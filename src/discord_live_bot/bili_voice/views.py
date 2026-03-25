from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

import discord
from loguru import logger

from ..rendering import error_embed
from .models import LiveRoomChoice

if TYPE_CHECKING:
    from ..bot import BiliDiscordBot


def _trim_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return text[:max_len]
    return f"{text[: max_len - 1]}..."


def _member_voice_channel(interaction: discord.Interaction) -> discord.VoiceChannel | discord.StageChannel | None:
    voice_state = getattr(interaction.user, "voice", None)
    if voice_state is None:
        return None
    channel = voice_state.channel
    if _looks_like_voice_channel(channel):
        return channel
    return None


def _looks_like_voice_channel(channel: object) -> bool:
    if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
        return True
    return hasattr(channel, "id") and hasattr(channel, "connect")


async def resolve_target_voice_channel(
    bot: "BiliDiscordBot",
    interaction: discord.Interaction,
) -> discord.VoiceChannel | discord.StageChannel | None:
    fixed_channel_id = getattr(bot.settings, "bili_voice_fixed_channel_id", None)
    if fixed_channel_id:
        channel = bot.get_channel(fixed_channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(fixed_channel_id)
            except Exception:
                return None
        if _looks_like_voice_channel(channel):
            return channel
        return None

    return _member_voice_channel(interaction)


class LiveRoomSelect(discord.ui.Select):
    def __init__(
        self,
        *,
        requester_id: int,
        rooms: list[LiveRoomChoice],
    ) -> None:
        options = []
        for room in rooms[:25]:
            label = _trim_text(room.uname, 100)
            description = _trim_text(room.title or f"Room {room.room_id}", 100)
            options.append(
                discord.SelectOption(
                    label=label,
                    description=description,
                    value=room.uid,
                )
            )

        super().__init__(
            placeholder="Select a live streamer / 选择正在直播的主播",
            min_values=1,
            max_values=1,
            options=options,
        )
        self._requester_id = requester_id

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, LiveRoomSelectView):
            await interaction.response.send_message(
                embed=error_embed("Voice selection is unavailable."),
                ephemeral=True,
            )
            return

        if interaction.user.id != self._requester_id:
            await interaction.response.send_message(
                embed=error_embed("Only the command user can use this selector."),
                ephemeral=True,
            )
            return

        await view.handle_selection(interaction, self.values[0])


class LiveRoomSelectView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: "BiliDiscordBot",
        requester_id: int,
        rooms: list[LiveRoomChoice],
        timeout: float = 900,
    ) -> None:
        super().__init__(timeout=timeout)
        self._bot = bot
        self._rooms_by_uid: Mapping[str, LiveRoomChoice] = {room.uid: room for room in rooms}
        self.add_item(LiveRoomSelect(requester_id=requester_id, rooms=rooms))

    async def handle_selection(self, interaction: discord.Interaction, uid: str) -> None:
        room = self._rooms_by_uid.get(uid)
        if room is None or interaction.guild is None:
            await interaction.response.send_message(
                embed=error_embed("Selected live room is unavailable."),
                ephemeral=True,
            )
            return

        voice_channel = await resolve_target_voice_channel(self._bot, interaction)
        if voice_channel is None:
            await interaction.response.send_message(
                embed=error_embed("Join a voice channel first or configure a fixed voice channel."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            session = await self._bot.voice_manager.start_playback(
                guild=interaction.guild,
                voice_channel=voice_channel,
                room=room,
            )
        except Exception as exc:
            logger.warning("Failed to start Bilibili voice playback uid={}: {}", uid, exc)
            await interaction.followup.send(
                embed=error_embed(f"Failed to start voice playback: {exc}"),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Voice Playback Started",
            description=(
                f"Playing **{session.uname}** in <#{session.channel_id}>.\n"
                f"Title: {session.title or 'No title'}"
            ),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
