from __future__ import annotations

import asyncio
from collections import defaultdict
import subprocess

import discord

from ..config import Settings
from .models import LiveRoomChoice, VoiceSession
from .resolver import ensure_ffmpeg_available, open_streamlink_stdout, resolve_stream_url


class StreamlinkFFmpegPCMAudio(discord.FFmpegPCMAudio):
    def __init__(
        self,
        streamlink_process: subprocess.Popen[bytes],
        *,
        executable: str,
    ) -> None:
        self._streamlink_process = streamlink_process
        super().__init__(
            streamlink_process.stdout,
            executable=executable,
            pipe=True,
            before_options="-nostdin",
            options="-vn",
        )

    def cleanup(self) -> None:
        super().cleanup()
        try:
            if self._streamlink_process.stdout is not None:
                self._streamlink_process.stdout.close()
        except Exception:
            pass
        try:
            self._streamlink_process.terminate()
        except Exception:
            pass
        try:
            self._streamlink_process.wait(timeout=3)
        except Exception:
            try:
                self._streamlink_process.kill()
            except Exception:
                pass


class BiliVoiceManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._sessions: dict[int, VoiceSession] = {}

    async def start_playback(
        self,
        *,
        guild: discord.Guild,
        voice_channel: discord.VoiceChannel | discord.StageChannel,
        room: LiveRoomChoice,
    ) -> VoiceSession:
        async with self._locks[guild.id]:
            quality, _ = await resolve_stream_url(
                room.room_url,
                self._settings.bili_voice_streamlink_quality,
            )
            ffmpeg_path = ensure_ffmpeg_available(self._settings.bili_voice_ffmpeg_path)
            streamlink_process = open_streamlink_stdout(room.room_url, quality)

            voice_client = guild.voice_client
            if voice_client is None or not voice_client.is_connected():
                voice_client = await voice_channel.connect()
            elif voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)

            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()

            source = StreamlinkFFmpegPCMAudio(
                streamlink_process,
                executable=ffmpeg_path,
            )
            voice_client.play(source)

            session = VoiceSession(
                guild_id=guild.id,
                channel_id=voice_channel.id,
                uid=room.uid,
                uname=room.uname,
                title=room.title,
                room_url=room.room_url,
            )
            self._sessions[guild.id] = session
            return session

    async def stop_playback(self, guild: discord.Guild) -> VoiceSession | None:
        async with self._locks[guild.id]:
            voice_client = guild.voice_client
            if voice_client is not None and (voice_client.is_playing() or voice_client.is_paused()):
                voice_client.stop()
            return self._sessions.get(guild.id)

    async def leave_voice(self, guild: discord.Guild) -> VoiceSession | None:
        async with self._locks[guild.id]:
            session = self._sessions.pop(guild.id, None)
            voice_client = guild.voice_client
            if voice_client is not None and voice_client.is_connected():
                await voice_client.disconnect()
            return session

    def get_session(self, guild_id: int) -> VoiceSession | None:
        return self._sessions.get(guild_id)

    async def aclose(self, bot: discord.Client) -> None:
        guild_ids = list(self._sessions)
        for guild_id in guild_ids:
            guild = bot.get_guild(guild_id)
            if guild is None:
                continue
            await self.leave_voice(guild)
