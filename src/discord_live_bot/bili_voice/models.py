from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LiveRoomChoice:
    uid: str
    uname: str
    title: str
    room_url: str
    room_id: int
    short_id: int


@dataclass
class VoiceSession:
    guild_id: int
    channel_id: int
    uid: str
    uname: str
    title: str
    room_url: str
