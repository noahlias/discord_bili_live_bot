from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from ..rendering import error_embed
from .views import LiveRoomSelectView, resolve_target_voice_channel


def _info_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.blurple())


class BiliVoiceCog(commands.Cog):
    def __init__(self, bot: "discord.Client") -> None:
        self.bot = bot

    @app_commands.command(name="voice_live", description="Pick a live subscribed Bilibili streamer to play in voice")
    async def voice_live(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(embed=error_embed("This command only works in a guild."), ephemeral=True)
            return
        if await resolve_target_voice_channel(self.bot, interaction) is None:
            await interaction.followup.send(
                embed=error_embed("Join a voice channel first or configure a fixed voice channel."),
                ephemeral=True,
            )
            return

        uids = self.bot.store.list_uids()
        if not uids:
            await interaction.followup.send(
                embed=_info_embed("No subscriptions", "Use `/subscribe uid` first."),
                ephemeral=True,
            )
            return

        try:
            rooms = await self.bot.voice_service.list_live_rooms(uids)
        except Exception as exc:
            logger.warning("Failed to fetch live rooms for voice selection: {}", exc)
            await interaction.followup.send(
                embed=error_embed(f"Failed to fetch live subscriptions: {exc}"),
                ephemeral=True,
            )
            return

        if not rooms:
            await interaction.followup.send(
                embed=_info_embed("No live subscriptions", "No subscribed Bilibili users are live right now."),
                ephemeral=True,
            )
            return

        view = LiveRoomSelectView(bot=self.bot, requester_id=interaction.user.id, rooms=rooms)
        embed = discord.Embed(
            title="Select Live Stream Audio",
            description="Choose one currently live subscribed streamer to play in your voice channel.",
            color=discord.Color.blurple(),
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="voice_stop", description="Stop the current Bilibili live audio playback")
    async def voice_stop(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(embed=error_embed("This command only works in a guild."), ephemeral=True)
            return

        session = await self.bot.voice_manager.stop_playback(interaction.guild)
        if session is None:
            await interaction.followup.send(
                embed=_info_embed("Nothing playing", "No active voice playback session exists for this guild."),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=_info_embed("Playback stopped", f"Stopped **{session.uname}**."),
            ephemeral=True,
        )

    @app_commands.command(name="voice_leave", description="Disconnect the bot from the current voice channel")
    async def voice_leave(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(embed=error_embed("This command only works in a guild."), ephemeral=True)
            return

        session = await self.bot.voice_manager.leave_voice(interaction.guild)
        if session is None and interaction.guild.voice_client is None:
            await interaction.followup.send(
                embed=_info_embed("Not connected", "The bot is not connected to a voice channel."),
                ephemeral=True,
            )
            return

        name = session.uname if session is not None else "current session"
        await interaction.followup.send(
            embed=_info_embed("Left voice", f"Disconnected after **{name}**."),
            ephemeral=True,
        )
