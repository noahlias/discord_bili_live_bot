from __future__ import annotations

import pytest

from discord_live_bot.bili_voice.manager import BiliVoiceManager
from discord_live_bot.bili_voice.models import LiveRoomChoice
from discord_live_bot.config import Settings


class _FakeVoiceClient:
    def __init__(self, channel) -> None:
        self.channel = channel
        self._is_connected = True
        self._is_playing = False
        self._is_paused = False
        self.play_calls = []
        self.stop_calls = 0
        self.move_calls = []
        self.disconnect_calls = 0

    def is_connected(self):
        return self._is_connected

    def is_playing(self):
        return self._is_playing

    def is_paused(self):
        return self._is_paused

    def play(self, source):
        self.play_calls.append(source)
        self._is_playing = True

    def stop(self):
        self.stop_calls += 1
        self._is_playing = False

    async def move_to(self, channel):
        self.move_calls.append(channel.id)
        self.channel = channel

    async def disconnect(self):
        self.disconnect_calls += 1
        self._is_connected = False


class _FakeVoiceChannel:
    def __init__(self, guild, channel_id: int) -> None:
        self.guild = guild
        self.id = channel_id
        self.connect_calls = 0

    async def connect(self):
        self.connect_calls += 1
        voice_client = _FakeVoiceClient(self)
        self.guild.voice_client = voice_client
        return voice_client


class _FakeGuild:
    def __init__(self, guild_id: int) -> None:
        self.id = guild_id
        self.voice_client = None


class _FakeStreamProc:
    def __init__(self) -> None:
        self.stdout = object()


def _settings() -> Settings:
    return Settings(
        discord_token="x",
        notify_channel_id=1,
        guild_id=None,
        bili_voice_fixed_channel_id=None,
        poll_interval_seconds=30,
        dynamic_enabled=True,
        dynamic_poll_interval_seconds=60,
        dynamic_request_gap_seconds=0,
        dynamic_screenshot_enabled=True,
        dynamic_screenshot_template="https://example.com/{dyn_id}.jpg",
        dynamic_browser_screenshot_enabled=True,
        dynamic_browser_timeout_seconds=20,
        dynamic_browser_max_concurrency=1,
        dynamic_browser_args=("--disable-dev-shm-usage",),
        dynamic_browser_capture_url_template="https://m.bilibili.com/dynamic/{dyn_id}",
        dynamic_browser_long_screenshot_enabled=False,
        dynamic_browser_opus_fallback_enabled=True,
        dynamic_browser_opus_fallback_url_template="https://www.bilibili.com/opus/{dyn_id}",
        dynamic_browser_ua="test-ua",
        dynamic_captcha_address="",
        dynamic_captcha_token="harukabot",
        sqlite_path=":memory:",
        log_level="INFO",
        dota_enabled=True,
        dota_recent_match_limit=5,
        dota_http_timeout_seconds=15,
        bili_voice_enabled=True,
        bili_voice_streamlink_quality="audio_only",
        bili_voice_ffmpeg_path="",
    )


@pytest.mark.asyncio
async def test_start_playback_connects_and_plays(monkeypatch: pytest.MonkeyPatch):
    guild = _FakeGuild(1)
    channel = _FakeVoiceChannel(guild, 10)
    room = LiveRoomChoice(uid="1", uname="tester", title="live", room_url="https://live.bilibili.com/1", room_id=1, short_id=0)
    manager = BiliVoiceManager(_settings())

    async def fake_resolve(room_url, preferred_quality):
        del room_url, preferred_quality
        return "audio_only", "https://stream.example/live.m3u8"

    monkeypatch.setattr("discord_live_bot.bili_voice.manager.resolve_stream_url", fake_resolve)
    monkeypatch.setattr("discord_live_bot.bili_voice.manager.open_streamlink_stdout", lambda room_url, quality: _FakeStreamProc())
    monkeypatch.setattr("discord_live_bot.bili_voice.manager.ensure_ffmpeg_available", lambda path: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "discord_live_bot.bili_voice.manager.StreamlinkFFmpegPCMAudio",
        lambda *args, **kwargs: ("source", args, kwargs),
    )

    session = await manager.start_playback(guild=guild, voice_channel=channel, room=room)

    assert session.uid == "1"
    assert channel.connect_calls == 1
    assert guild.voice_client.play_calls
    assert manager.get_session(1) is not None


@pytest.mark.asyncio
async def test_stop_and_leave_voice(monkeypatch: pytest.MonkeyPatch):
    guild = _FakeGuild(1)
    channel = _FakeVoiceChannel(guild, 10)
    room = LiveRoomChoice(uid="1", uname="tester", title="live", room_url="https://live.bilibili.com/1", room_id=1, short_id=0)
    manager = BiliVoiceManager(_settings())

    async def fake_resolve(room_url, preferred_quality):
        del room_url, preferred_quality
        return "audio_only", "https://stream.example/live.m3u8"

    monkeypatch.setattr("discord_live_bot.bili_voice.manager.resolve_stream_url", fake_resolve)
    monkeypatch.setattr("discord_live_bot.bili_voice.manager.open_streamlink_stdout", lambda room_url, quality: _FakeStreamProc())
    monkeypatch.setattr("discord_live_bot.bili_voice.manager.ensure_ffmpeg_available", lambda path: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        "discord_live_bot.bili_voice.manager.StreamlinkFFmpegPCMAudio",
        lambda *args, **kwargs: ("source", args, kwargs),
    )

    await manager.start_playback(guild=guild, voice_channel=channel, room=room)
    session = await manager.stop_playback(guild)
    assert session is not None
    assert guild.voice_client.stop_calls == 1

    session = await manager.leave_voice(guild)
    assert session is not None
    assert guild.voice_client.disconnect_calls == 1
    assert manager.get_session(1) is None
