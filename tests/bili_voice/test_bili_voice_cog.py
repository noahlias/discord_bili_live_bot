from __future__ import annotations

import pytest

from discord_live_bot.bili_voice.cog import BiliVoiceCog
from discord_live_bot.bili_voice.models import LiveRoomChoice


class _DummyResponse:
    def __init__(self) -> None:
        self.deferred = False

    async def defer(self, *, thinking: bool, ephemeral: bool):
        assert thinking is True
        assert ephemeral is True
        self.deferred = True


class _DummyFollowup:
    def __init__(self) -> None:
        self.embeds = []
        self.views = []

    async def send(self, *, embed, ephemeral, view=None):
        self.embeds.append(embed)
        self.views.append(view)
        assert ephemeral is True


class _DummyVoiceState:
    def __init__(self, channel=None) -> None:
        self.channel = channel


class _DummyMember:
    def __init__(self, user_id: int, channel=None) -> None:
        self.id = user_id
        self.voice = _DummyVoiceState(channel)


class _DummyInteraction:
    def __init__(self, user, guild=None) -> None:
        self.user = user
        self.guild = guild
        self.response = _DummyResponse()
        self.followup = _DummyFollowup()


class _DummyStore:
    def __init__(self, uids=None) -> None:
        self._uids = list(uids or [])

    def list_uids(self):
        return list(self._uids)


class _DummyVoiceService:
    def __init__(self, rooms=None) -> None:
        self._rooms = list(rooms or [])

    async def list_live_rooms(self, uids):
        del uids
        return list(self._rooms)


class _DummyVoiceManager:
    async def stop_playback(self, guild):
        del guild
        return None

    async def leave_voice(self, guild):
        del guild
        return None


class _DummyBot:
    def __init__(self, *, store, voice_service, fixed_channel_id=None, fixed_channel=None) -> None:
        self.store = store
        self.voice_service = voice_service
        self.voice_manager = _DummyVoiceManager()
        self.settings = type("S", (), {"bili_voice_fixed_channel_id": fixed_channel_id})()
        self._fixed_channel = fixed_channel

    def get_channel(self, channel_id):
        if self._fixed_channel is not None and self._fixed_channel.id == channel_id:
            return self._fixed_channel
        return None

    async def fetch_channel(self, channel_id):
        if self._fixed_channel is not None and self._fixed_channel.id == channel_id:
            return self._fixed_channel
        raise RuntimeError("channel not found")


class _DummyChannel:
    def __init__(self, channel_id: int) -> None:
        self.id = channel_id

    async def connect(self):
        raise RuntimeError("not used in this test")


class _DummyGuild:
    def __init__(self) -> None:
        self.voice_client = None


@pytest.mark.asyncio
async def test_voice_live_requires_voice_channel():
    cog = BiliVoiceCog(_DummyBot(store=_DummyStore(["1"]), voice_service=_DummyVoiceService()))
    interaction = _DummyInteraction(_DummyMember(1, channel=None), guild=_DummyGuild())

    await cog.voice_live.callback(cog, interaction)

    assert interaction.response.deferred is True
    assert "Join a voice channel first" in interaction.followup.embeds[0].description


@pytest.mark.asyncio
async def test_voice_live_sends_live_room_selector():
    room = LiveRoomChoice(
        uid="1",
        uname="tester",
        title="live title",
        room_url="https://live.bilibili.com/1",
        room_id=1,
        short_id=0,
    )
    cog = BiliVoiceCog(
        _DummyBot(
            store=_DummyStore(["1"]),
            voice_service=_DummyVoiceService([room]),
        )
    )
    interaction = _DummyInteraction(_DummyMember(1, channel=_DummyChannel(10)), guild=_DummyGuild())

    await cog.voice_live.callback(cog, interaction)

    assert interaction.response.deferred is True
    assert interaction.followup.views[0] is not None
    assert interaction.followup.embeds[0].title == "Select Live Stream Audio"


@pytest.mark.asyncio
async def test_voice_live_uses_fixed_channel_without_member_voice():
    room = LiveRoomChoice(
        uid="1",
        uname="tester",
        title="live title",
        room_url="https://live.bilibili.com/1",
        room_id=1,
        short_id=0,
    )
    fixed_channel = _DummyChannel(1486273334521102376)
    cog = BiliVoiceCog(
        _DummyBot(
            store=_DummyStore(["1"]),
            voice_service=_DummyVoiceService([room]),
            fixed_channel_id=fixed_channel.id,
            fixed_channel=fixed_channel,
        )
    )
    interaction = _DummyInteraction(_DummyMember(1, channel=None), guild=_DummyGuild())

    await cog.voice_live.callback(cog, interaction)

    assert interaction.response.deferred is True
    assert interaction.followup.views[0] is not None
    assert interaction.followup.embeds[0].title == "Select Live Stream Audio"
