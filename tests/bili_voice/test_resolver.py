import subprocess

import pytest

from discord_live_bot.bili_voice.resolver import (
    VoiceDependencyError,
    VoiceStreamResolveError,
    _candidate_qualities,
    ensure_ffmpeg_available,
    ensure_streamlink_available,
    resolve_stream_url,
)


def test_candidate_qualities_deduplicates_and_prioritizes():
    assert _candidate_qualities("audio_only") == ["audio_only", "audio_mp4a", "audio_opus", "best"]


def test_ensure_ffmpeg_available_uses_path(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("discord_live_bot.bili_voice.resolver.shutil.which", lambda name: "/usr/bin/ffmpeg")
    assert ensure_ffmpeg_available("") == "/usr/bin/ffmpeg"


def test_ensure_streamlink_available_errors(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("discord_live_bot.bili_voice.resolver.shutil.which", lambda name: None)
    with pytest.raises(VoiceDependencyError):
        ensure_streamlink_available()


@pytest.mark.asyncio
async def test_resolve_stream_url_falls_back_to_second_quality(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("discord_live_bot.bili_voice.resolver.shutil.which", lambda name: f"/usr/bin/{name}")

    calls: list[list[str]] = []

    def fake_run(args, capture_output, check, text):
        del capture_output, check, text
        calls.append(args)
        quality = args[-1]
        if quality == "audio_only":
            raise subprocess.CalledProcessError(1, args, stderr="audio_only missing")

        class _Done:
            stdout = "https://stream.example/live.m3u8\n"

        return _Done()

    monkeypatch.setattr("discord_live_bot.bili_voice.resolver.subprocess.run", fake_run)

    quality, stream_url = await resolve_stream_url("https://live.bilibili.com/11", "audio_only")

    assert quality == "audio_mp4a"
    assert stream_url == "https://stream.example/live.m3u8"
    assert calls[0][-1] == "audio_only"
    assert calls[1][-1] == "audio_mp4a"


@pytest.mark.asyncio
async def test_resolve_stream_url_raises_after_all_candidates_fail(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("discord_live_bot.bili_voice.resolver.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(args, capture_output, check, text):
        del capture_output, check, text
        raise subprocess.CalledProcessError(1, args, stderr="boom")

    monkeypatch.setattr("discord_live_bot.bili_voice.resolver.subprocess.run", fake_run)

    with pytest.raises(VoiceStreamResolveError):
        await resolve_stream_url("https://live.bilibili.com/11", "audio_only")
