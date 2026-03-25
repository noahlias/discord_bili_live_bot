from __future__ import annotations

from .models import LiveRoomChoice
from ..bili_client import BiliClient, RoomInfo


class BiliVoiceService:
    def __init__(self, bili_client: BiliClient) -> None:
        self._bili_client = bili_client

    async def list_live_rooms(self, uids: list[str]) -> list[LiveRoomChoice]:
        if not uids:
            return []

        rooms = await self._bili_client.fetch_rooms(uids)
        live_rooms = [room for room in rooms.values() if room.live_status]
        live_rooms.sort(key=lambda room: room.uname.lower())
        return [self._to_choice(room) for room in live_rooms]

    @staticmethod
    def _to_choice(room: RoomInfo) -> LiveRoomChoice:
        return LiveRoomChoice(
            uid=room.uid,
            uname=room.uname,
            title=room.title,
            room_url=room.room_url,
            room_id=room.room_id,
            short_id=room.short_id,
        )
