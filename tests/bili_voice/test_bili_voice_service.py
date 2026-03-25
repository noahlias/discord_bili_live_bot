import pytest

from discord_live_bot.bili_client import RoomInfo
from discord_live_bot.bili_voice.service import BiliVoiceService


class _FakeBiliClient:
    async def fetch_rooms(self, uids):
        del uids
        return {
            "2": RoomInfo(
                uid="2",
                uname="zzz",
                live_status=1,
                room_id=22,
                short_id=0,
                title="live room z",
                cover="",
                face="",
                area_parent="game",
                area_name="moba",
                live_time=1,
            ),
            "1": RoomInfo(
                uid="1",
                uname="aaa",
                live_status=1,
                room_id=11,
                short_id=0,
                title="live room a",
                cover="",
                face="",
                area_parent="game",
                area_name="moba",
                live_time=1,
            ),
            "3": RoomInfo(
                uid="3",
                uname="offline",
                live_status=0,
                room_id=33,
                short_id=0,
                title="offline",
                cover="",
                face="",
                area_parent="game",
                area_name="moba",
                live_time=None,
            ),
        }


@pytest.mark.asyncio
async def test_list_live_rooms_filters_and_sorts():
    service = BiliVoiceService(_FakeBiliClient())

    rooms = await service.list_live_rooms(["1", "2", "3"])

    assert [room.uid for room in rooms] == ["1", "2"]
    assert rooms[0].title == "live room a"
    assert rooms[0].room_url == "https://live.bilibili.com/11"
