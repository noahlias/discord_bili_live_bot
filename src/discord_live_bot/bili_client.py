from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class RoomInfo:
    uid: str
    uname: str
    live_status: int
    room_id: int
    short_id: int
    title: str
    cover: str
    face: str
    area_parent: str
    area_name: str
    live_time: int | None

    @property
    def room_url(self) -> str:
        room_id = self.short_id or self.room_id
        return f"https://live.bilibili.com/{room_id}"

    @property
    def profile_url(self) -> str:
        return f"https://space.bilibili.com/{self.uid}"


class BiliClient:
    _api_url = "https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids"

    def __init__(self, timeout_seconds: float = 15.0):
        self._timeout_seconds = timeout_seconds

    async def fetch_rooms(self, uids: Sequence[str]) -> dict[str, RoomInfo]:
        if not uids:
            return {}
        raw = await self._fetch_with_httpx(uids)
        return self._normalize_rooms(raw)

    async def _fetch_with_httpx(self, uids: Sequence[str]) -> dict[str, Any]:
        payload_uids: list[int | str] = []
        for uid in uids:
            if uid.isdigit():
                payload_uids.append(int(uid))
            else:
                payload_uids.append(uid)

        payload = {"uids": payload_uids}
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
        }

        async with httpx.AsyncClient(timeout=self._timeout_seconds, headers=headers) as client:
            response = await client.post(self._api_url, json=payload)
            response.raise_for_status()
            body = response.json()

        if body.get("code") != 0:
            raise RuntimeError(f"Bilibili API error: code={body.get('code')}")
        data = body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("Bilibili API returned invalid payload")
        return data

    def _normalize_rooms(self, raw: dict[str, Any]) -> dict[str, RoomInfo]:
        normalized: dict[str, RoomInfo] = {}
        for uid, info in raw.items():
            if not isinstance(info, dict):
                continue
            uid_str = str(uid)
            live_status = self._to_int(info.get("live_status"))
            if live_status == 2:
                live_status = 0
            room_id = self._to_int(info.get("room_id"))
            short_id = self._to_int(info.get("short_id"))
            cover = self._normalize_url(info.get("cover_from_user") or info.get("keyframe"))
            normalized[uid_str] = RoomInfo(
                uid=uid_str,
                uname=str(info.get("uname") or uid_str),
                live_status=live_status,
                room_id=room_id,
                short_id=short_id,
                title=str(info.get("title") or ""),
                cover=cover,
                face=self._normalize_url(info.get("face")),
                area_parent=str(info.get("area_v2_parent_name") or "未知"),
                area_name=str(info.get("area_v2_name") or "未知"),
                live_time=self._to_optional_int(info.get("live_time")),
            )
        return normalized

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_optional_int(value: Any) -> int | None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _normalize_url(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if raw.startswith("//"):
            raw = f"https:{raw}"
        elif raw.startswith("http://"):
            raw = f"https://{raw[len('http://'):]}"

        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"}:
            return ""
        if not parsed.netloc:
            return ""
        return raw
