from __future__ import annotations

import time
from dataclasses import dataclass

from .bili_client import RoomInfo


@dataclass(frozen=True)
class StatusChange:
    uid: str
    room: RoomInfo
    went_live: bool
    duration_seconds: int | None


class StatusTracker:
    def __init__(self) -> None:
        self._status: dict[str, int] = {}
        self._live_started_at: dict[str, int] = {}

    def prune(self, active_uids: list[str]) -> None:
        active = set(active_uids)
        stale = [uid for uid in self._status if uid not in active]
        for uid in stale:
            self._status.pop(uid, None)
            self._live_started_at.pop(uid, None)

    def diff(self, snapshot: dict[str, RoomInfo], now_ts: int | None = None) -> list[StatusChange]:
        now = now_ts if now_ts is not None else int(time.time())
        changes: list[StatusChange] = []

        for uid, room in snapshot.items():
            new_status = 1 if room.live_status else 0
            old_status = self._status.get(uid)
            if old_status is None:
                self._status[uid] = new_status
                if new_status:
                    self._live_started_at[uid] = room.live_time or now
                continue

            if old_status == new_status:
                if new_status and uid not in self._live_started_at:
                    self._live_started_at[uid] = room.live_time or now
                continue

            self._status[uid] = new_status
            if new_status:
                self._live_started_at[uid] = room.live_time or now
                changes.append(
                    StatusChange(uid=uid, room=room, went_live=True, duration_seconds=None)
                )
                continue

            started_at = self._live_started_at.pop(uid, None)
            duration_seconds: int | None = None
            if started_at is not None and now >= started_at:
                duration_seconds = now - started_at
            changes.append(
                StatusChange(
                    uid=uid,
                    room=room,
                    went_live=False,
                    duration_seconds=duration_seconds,
                )
            )

        return changes
