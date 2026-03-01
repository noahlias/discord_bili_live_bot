from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from loguru import logger

from .bili_client import BiliClient, RoomInfo
from .config import Settings
from .db import SubscriptionStore
from .rendering import (
    empty_state_embed,
    error_embed,
    live_end_embed,
    live_start_embed,
    live_start_view,
    snapshot_embeds,
)
from .status_tracker import StatusTracker


def _ok_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc),
    )


def _info_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )


class SubscriptionCog(commands.Cog):
    def __init__(self, bot: "BiliDiscordBot"):
        self.bot = bot

    @app_commands.command(name="subscribe", description="Subscribe to a Bilibili UID")
    @app_commands.describe(uid="Bilibili UID")
    async def subscribe(self, interaction: discord.Interaction, uid: str) -> None:
        uid = uid.strip()
        if not uid.isdigit():
            await interaction.response.send_message(
                embed=error_embed("UID must be numeric / UID 必须是数字。"),
                ephemeral=True,
            )
            return

        inserted = self.bot.store.add_uid(uid)
        if inserted:
            embed = _ok_embed(
                "Subscribed / 订阅成功",
                f"Now following **{uid}**.\nUse `/list` to view all subscriptions.",
            )
        else:
            embed = _info_embed(
                "Already subscribed / 已订阅",
                f"UID **{uid}** is already in your subscription list.",
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="unsubscribe", description="Unsubscribe a Bilibili UID")
    @app_commands.describe(uid="Bilibili UID")
    async def unsubscribe(self, interaction: discord.Interaction, uid: str) -> None:
        uid = uid.strip()
        if not uid.isdigit():
            await interaction.response.send_message(
                embed=error_embed("UID must be numeric / UID 必须是数字。"),
                ephemeral=True,
            )
            return

        removed = self.bot.store.remove_uid(uid)
        if removed:
            embed = _ok_embed("Unsubscribed / 取消订阅", f"Removed **{uid}** from subscription list.")
        else:
            embed = _info_embed(
                "Not found / 未找到",
                f"UID **{uid}** is not in your current subscription list.",
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @unsubscribe.autocomplete("uid")
    async def unsubscribe_uid_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        del interaction
        return self._autocomplete_uid_choices(current)

    @app_commands.command(name="list", description="Show all subscriptions")
    async def list_subscriptions(self, interaction: discord.Interaction) -> None:
        await self._send_snapshot(interaction, live_only=False)

    @app_commands.command(name="live", description="Show currently live subscriptions")
    async def list_live(self, interaction: discord.Interaction) -> None:
        await self._send_snapshot(interaction, live_only=True)

    @app_commands.command(name="help", description="Show available commands")
    async def help_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Commands / 命令",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="/subscribe uid", value="Follow a Bilibili UID / 订阅用户", inline=False)
        embed.add_field(name="/unsubscribe uid", value="Unfollow a UID / 取消订阅", inline=False)
        embed.add_field(name="/list", value="Show all followed users / 查看全部订阅", inline=False)
        embed.add_field(name="/live", value="Show users currently live / 查看当前开播", inline=False)
        embed.add_field(name="/help", value="Show command help", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _send_snapshot(self, interaction: discord.Interaction, *, live_only: bool) -> None:
        await interaction.response.defer(thinking=True)

        uids = self.bot.store.list_uids()
        if not uids:
            await interaction.followup.send(embed=empty_state_embed())
            return

        try:
            rooms = await self.bot.bili_client.fetch_rooms(uids)
        except Exception as exc:
            logger.exception("Failed to fetch room info for /list or /live")
            await interaction.followup.send(embed=error_embed(f"Failed to fetch live data: {exc}"))
            return

        display_rooms: list[RoomInfo] = list(rooms.values())
        if live_only:
            display_rooms = [room for room in display_rooms if room.live_status]

        embeds = snapshot_embeds(display_rooms, len(uids), live_only=live_only)
        for embed in embeds:
            await interaction.followup.send(embed=embed)

    def _autocomplete_uid_choices(self, current: str) -> list[app_commands.Choice[str]]:
        typed = current.strip()
        uids = self.bot.store.list_uids()

        if not typed:
            matches = uids
        else:
            starts_with = [uid for uid in uids if uid.startswith(typed)]
            contains = [uid for uid in uids if typed in uid and not uid.startswith(typed)]
            matches = starts_with + contains

        return [app_commands.Choice(name=uid, value=uid) for uid in matches[:25]]


class BiliDiscordBot(commands.Bot):
    def __init__(
        self,
        settings: Settings,
        store: SubscriptionStore,
        bili_client: BiliClient,
        tracker: StatusTracker,
    ):
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings
        self.store = store
        self.bili_client = bili_client
        self.tracker = tracker

    async def setup_hook(self) -> None:
        await self.add_cog(SubscriptionCog(self))

        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced slash commands to guild {}", self.settings.guild_id)
        else:
            await self.tree.sync()
            logger.info("Synced slash commands globally")

        self.poll_live_status.change_interval(seconds=self.settings.poll_interval_seconds)
        self.poll_live_status.start()

    async def close(self) -> None:
        if self.poll_live_status.is_running():
            self.poll_live_status.cancel()
        self.store.close()
        await super().close()

    @tasks.loop(seconds=30)
    async def poll_live_status(self) -> None:
        uids = self.store.list_uids()
        self.tracker.prune(uids)
        if not uids:
            return

        try:
            snapshot = await self.bili_client.fetch_rooms(uids)
        except Exception:
            logger.exception("Failed to fetch room info in scheduler")
            return
        if not snapshot:
            return

        changes = self.tracker.diff(snapshot)
        if not changes:
            return

        channel = self.get_channel(self.settings.notify_channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(self.settings.notify_channel_id)
            except Exception:
                logger.exception("Failed to fetch notify channel {}", self.settings.notify_channel_id)
                return

        for change in changes:
            try:
                now = datetime.now(timezone.utc)
                if change.went_live:
                    await channel.send(
                        embed=live_start_embed(change.room, now),
                        view=live_start_view(change.room),
                    )
                else:
                    await channel.send(
                        embed=live_end_embed(change.room, change.duration_seconds, now)
                    )
            except Exception:
                logger.exception("Failed to send transition message for uid {}", change.uid)

    @poll_live_status.before_loop
    async def _before_poll(self) -> None:
        await self.wait_until_ready()
