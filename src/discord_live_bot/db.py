from __future__ import annotations

import sqlite3
import time
from collections.abc import Sequence
from pathlib import Path


class SubscriptionStore:
    def __init__(self, db_path: str):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                uid TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dynamic_offsets (
                uid TEXT PRIMARY KEY,
                last_dyn_id INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dota_searches (
                account_id TEXT PRIMARY KEY,
                persona_name TEXT NOT NULL,
                search_count INTEGER NOT NULL,
                last_searched_at INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def add_uid(self, uid: str) -> bool:
        now = int(time.time())
        cursor = self._conn.execute(
            "INSERT OR IGNORE INTO subscriptions(uid, created_at) VALUES (?, ?)",
            (uid, now),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def remove_uid(self, uid: str) -> bool:
        cursor = self._conn.execute("DELETE FROM subscriptions WHERE uid = ?", (uid,))
        self._conn.execute("DELETE FROM dynamic_offsets WHERE uid = ?", (uid,))
        self._conn.commit()
        return cursor.rowcount > 0

    def list_uids(self) -> list[str]:
        rows = self._conn.execute("SELECT uid FROM subscriptions ORDER BY created_at ASC").fetchall()
        return [row[0] for row in rows]

    def get_dynamic_offset(self, uid: str) -> int | None:
        row = self._conn.execute(
            "SELECT last_dyn_id FROM dynamic_offsets WHERE uid = ?",
            (uid,),
        ).fetchone()
        if row is None:
            return None
        return int(row[0])

    def upsert_dynamic_offset(self, uid: str, last_dyn_id: int) -> None:
        now = int(time.time())
        self._conn.execute(
            """
            INSERT INTO dynamic_offsets(uid, last_dyn_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
              last_dyn_id = excluded.last_dyn_id,
              updated_at = excluded.updated_at
            """,
            (uid, int(last_dyn_id), now),
        )
        self._conn.commit()

    def delete_dynamic_offset(self, uid: str) -> None:
        self._conn.execute("DELETE FROM dynamic_offsets WHERE uid = ?", (uid,))
        self._conn.commit()

    def prune_dynamic_offsets(self, valid_uids: Sequence[str]) -> None:
        if not valid_uids:
            self._conn.execute("DELETE FROM dynamic_offsets")
            self._conn.commit()
            return
        placeholders = ", ".join("?" for _ in valid_uids)
        self._conn.execute(
            f"DELETE FROM dynamic_offsets WHERE uid NOT IN ({placeholders})",
            tuple(valid_uids),
        )
        self._conn.commit()

    def record_dota_search(self, account_id: str, persona_name: str) -> None:
        account = account_id.strip()
        if not account:
            return

        now = int(time.time())
        display_name = persona_name.strip()
        self._conn.execute(
            """
            INSERT INTO dota_searches(account_id, persona_name, search_count, last_searched_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(account_id) DO UPDATE SET
              persona_name = CASE
                  WHEN excluded.persona_name <> '' THEN excluded.persona_name
                  ELSE dota_searches.persona_name
              END,
              search_count = dota_searches.search_count + 1,
              last_searched_at = excluded.last_searched_at
            """,
            (account, display_name, now),
        )
        self._conn.commit()

    def list_dota_searches(
        self,
        query: str = "",
        *,
        limit: int = 25,
    ) -> list[tuple[str, str, int]]:
        safe_limit = max(1, min(int(limit), 100))
        typed = query.strip()
        if not typed:
            rows = self._conn.execute(
                """
                SELECT account_id, persona_name, search_count
                FROM dota_searches
                ORDER BY search_count DESC, last_searched_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        else:
            account_contains = f"%{typed}%"
            account_prefix = f"{typed}%"
            lowered = typed.lower()
            name_contains = f"%{lowered}%"
            name_prefix = f"{lowered}%"
            rows = self._conn.execute(
                """
                SELECT account_id, persona_name, search_count
                FROM dota_searches
                WHERE account_id LIKE ? OR lower(persona_name) LIKE ?
                ORDER BY
                  CASE
                    WHEN account_id LIKE ? THEN 0
                    WHEN lower(persona_name) LIKE ? THEN 1
                    ELSE 2
                  END,
                  search_count DESC,
                  last_searched_at DESC
                LIMIT ?
                """,
                (
                    account_contains,
                    name_contains,
                    account_prefix,
                    name_prefix,
                    safe_limit,
                ),
            ).fetchall()

        return [(str(account), str(name or ""), int(count)) for account, name, count in rows]

    def close(self) -> None:
        self._conn.close()
