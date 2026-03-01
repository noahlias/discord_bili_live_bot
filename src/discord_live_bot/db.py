from __future__ import annotations

import sqlite3
import time
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
        self._conn.commit()
        return cursor.rowcount > 0

    def list_uids(self) -> list[str]:
        rows = self._conn.execute("SELECT uid FROM subscriptions ORDER BY created_at ASC").fetchall()
        return [row[0] for row in rows]

    def close(self) -> None:
        self._conn.close()
