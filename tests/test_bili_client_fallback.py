import pytest

from discord_live_bot.bili_client import BiliClient


@pytest.mark.asyncio
async def test_bili_client_fetch_uses_httpx(monkeypatch):
    client = BiliClient()
    calls = {"httpx": 0}

    async def fake_httpx(_uids):
        calls["httpx"] += 1
        return {
            "2": {
                "uname": "tester",
                "live_status": 1,
                "room_id": 22,
                "short_id": 0,
                "title": "hello",
                "cover_from_user": "cover",
                "face": "face",
                "area_v2_parent_name": "game",
                "area_v2_name": "fps",
                "live_time": 100,
            }
        }

    monkeypatch.setattr(client, "_fetch_with_httpx", fake_httpx)

    rooms = await client.fetch_rooms(["2"])

    assert calls["httpx"] == 1
    assert rooms["2"].uname == "tester"
    assert rooms["2"].live_status == 1


@pytest.mark.asyncio
async def test_bili_client_normalizes_status_two_to_offline(monkeypatch):
    client = BiliClient()

    async def fake_httpx(_uids):
        return {
            "3": {
                "uname": "tester2",
                "live_status": 2,
                "room_id": 33,
                "short_id": 0,
            }
        }

    monkeypatch.setattr(client, "_fetch_with_httpx", fake_httpx)

    rooms = await client.fetch_rooms(["3"])
    assert rooms["3"].live_status == 0


@pytest.mark.asyncio
async def test_bili_client_normalizes_cover_and_face_urls(monkeypatch):
    client = BiliClient()

    async def fake_httpx(_uids):
        return {
            "4": {
                "uname": "tester3",
                "live_status": 1,
                "room_id": 44,
                "short_id": 0,
                "cover_from_user": "//i0.hdslb.com/bfs/live/cover.jpg",
                "face": "http://i0.hdslb.com/bfs/face/avatar.jpg",
            }
        }

    monkeypatch.setattr(client, "_fetch_with_httpx", fake_httpx)

    rooms = await client.fetch_rooms(["4"])
    assert rooms["4"].cover.startswith("https://")
    assert rooms["4"].face.startswith("https://")
