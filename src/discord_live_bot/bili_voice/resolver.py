from __future__ import annotations

import asyncio
import shutil
import subprocess


class VoiceDependencyError(RuntimeError):
    """Raised when required audio dependencies are not available."""


class VoiceStreamResolveError(RuntimeError):
    """Raised when a livestream cannot be resolved to a playable URL."""


def ensure_ffmpeg_available(explicit_path: str = "") -> str:
    if explicit_path:
        return explicit_path
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise VoiceDependencyError("ffmpeg is required for voice playback but was not found on PATH.")
    return ffmpeg_path


def ensure_streamlink_available() -> str:
    streamlink_path = shutil.which("streamlink")
    if streamlink_path is None:
        raise VoiceDependencyError("streamlink is required for live audio playback but was not found on PATH.")
    return streamlink_path


def _candidate_qualities(preferred_quality: str) -> list[str]:
    candidates = [preferred_quality.strip() or "audio_only", "audio_only", "audio_mp4a", "audio_opus", "best"]
    seen: set[str] = set()
    result: list[str] = []
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def _resolve_stream_url_sync(room_url: str, preferred_quality: str) -> tuple[str, str]:
    streamlink_path = ensure_streamlink_available()

    last_error = "unknown streamlink error"
    for quality in _candidate_qualities(preferred_quality):
        try:
            completed = subprocess.run(
                [streamlink_path, "--stream-url", room_url, quality],
                capture_output=True,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or exc.stdout or "").strip()
            if stderr:
                last_error = stderr
            continue

        stream_url = (completed.stdout or "").strip()
        if stream_url:
            return quality, stream_url
        last_error = "streamlink returned an empty stream url"

    raise VoiceStreamResolveError(f"Failed to resolve playable stream url: {last_error}")


async def resolve_stream_url(room_url: str, preferred_quality: str) -> tuple[str, str]:
    return await asyncio.to_thread(_resolve_stream_url_sync, room_url, preferred_quality)


def open_streamlink_stdout(room_url: str, quality: str) -> subprocess.Popen[bytes]:
    streamlink_path = ensure_streamlink_available()
    process = subprocess.Popen(
        [streamlink_path, "--stdout", room_url, quality],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None:
        raise VoiceStreamResolveError("streamlink stdout pipe was not created")
    return process
