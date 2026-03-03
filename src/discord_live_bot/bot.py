from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from loguru import logger

from .bili_client import BiliClient, RoomInfo
from .config import Settings
from .db import SubscriptionStore
from .dynamic_client import DynamicClient, DynamicFetchError
from .dynamic_screenshot import DynamicScreenshotter
from .rendering import (
    dynamic_post_embed,
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
        embed.add_field(
            name="/test_dynamic_push [uid]",
            value="Send latest dynamic preview to notify channel / 推送动态测试",
            inline=False,
        )
        embed.add_field(name="/help", value="Show command help", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="test_dynamic_push",
        description="Push latest dynamic for testing to notify channel",
    )
    @app_commands.describe(uid="Optional Bilibili UID (default: first subscribed or 7261854)")
    async def test_dynamic_push(self, interaction: discord.Interaction, uid: str | None = None) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        target_uid = (uid or "").strip()
        if not target_uid:
            subscribed = self.bot.store.list_uids()
            target_uid = subscribed[0] if subscribed else "7261854"
        if not target_uid.isdigit():
            await interaction.followup.send(
                embed=error_embed("UID must be numeric / UID 必须是数字。"),
                ephemeral=True,
            )
            return

        channel = await self.bot._resolve_notify_channel()
        if channel is None:
            await interaction.followup.send(
                embed=error_embed("Failed to resolve notify channel / 通知频道获取失败。"),
                ephemeral=True,
            )
            return

        try:
            dynamics = await self.bot.dynamic_client.fetch_user_dynamics(target_uid)
        except DynamicFetchError as exc:
            await interaction.followup.send(
                embed=error_embed(f"Dynamic fetch failed: {exc}"),
                ephemeral=True,
            )
            return
        except Exception as exc:
            logger.exception("Unexpected error in /test_dynamic_push")
            await interaction.followup.send(
                embed=error_embed(f"Unexpected error: {exc}"),
                ephemeral=True,
            )
            return

        if not dynamics:
            await interaction.followup.send(
                embed=_info_embed(
                    "No dynamics / 无动态",
                    f"UID **{target_uid}** has no readable dynamics right now.",
                ),
                ephemeral=True,
            )
            return

        item = max(dynamics, key=lambda value: value.dyn_id)
        embed, file = await self.bot._build_dynamic_message(item, datetime.now(timezone.utc))
        try:
            if file is not None:
                await channel.send(embed=embed, file=file)
            else:
                await channel.send(embed=embed)
        except Exception:
            logger.exception("Failed to send /test_dynamic_push message")
            await interaction.followup.send(
                embed=error_embed("Failed to send message to notify channel / 推送失败。"),
                ephemeral=True,
            )
            return

        channel_id = getattr(channel, "id", self.bot.settings.notify_channel_id)
        await interaction.followup.send(
            embed=_ok_embed(
                "Dynamic test sent / 动态测试已发送",
                f"UID **{target_uid}**, dynamic **{item.dyn_id}** sent to <#{channel_id}>.",
            ),
            ephemeral=True,
        )

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
        dynamic_client: DynamicClient,
        tracker: StatusTracker,
    ):
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings
        self.store = store
        self.bili_client = bili_client
        self.dynamic_client = dynamic_client
        self.dynamic_screenshotter = DynamicScreenshotter(settings)
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
        if self.settings.dynamic_enabled:
            self.poll_dynamic_status.change_interval(
                seconds=self.settings.dynamic_poll_interval_seconds
            )
            self.poll_dynamic_status.start()

    async def close(self) -> None:
        if self.poll_live_status.is_running():
            self.poll_live_status.cancel()
        if self.poll_dynamic_status.is_running():
            self.poll_dynamic_status.cancel()
        await self.dynamic_screenshotter.aclose()
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

    async def _resolve_notify_channel(self) -> discord.abc.Messageable | None:
        channel = self.get_channel(self.settings.notify_channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(self.settings.notify_channel_id)
            except Exception:
                logger.exception("Failed to fetch notify channel {}", self.settings.notify_channel_id)
                return None
        return channel

    def _dynamic_screenshot_url(self, uid: str, dyn_id: int, dynamic_url: str) -> str:
        if not self.settings.dynamic_screenshot_enabled:
            return ""
        template = self.settings.dynamic_screenshot_template
        try:
            return template.format(uid=uid, dyn_id=dyn_id, dynamic_url=dynamic_url)
        except Exception:
            logger.warning("Invalid BILI_DYNAMIC_SCREENSHOT_TEMPLATE, fallback to empty image url")
            return ""

    async def _build_dynamic_message(self, item, now: datetime) -> tuple[discord.Embed, discord.File | None]:
        image_url = item.cover_url or self._dynamic_screenshot_url(item.uid, item.dyn_id, item.dynamic_url)
        attachment: discord.File | None = None

        if self.settings.dynamic_screenshot_enabled and self.settings.dynamic_browser_screenshot_enabled:
            screenshot = await self.dynamic_screenshotter.capture(item.dyn_id, item.dynamic_url)
            if screenshot.image_bytes:
                file_name = f"dynamic_{item.dyn_id}.jpg"
                attachment = discord.File(io.BytesIO(screenshot.image_bytes), filename=file_name)
                image_url = f"attachment://{file_name}"

        return dynamic_post_embed(item, now, image_url=image_url), attachment

    @tasks.loop(seconds=60)
    async def poll_dynamic_status(self) -> None:
        await self._poll_dynamic_once()

    async def _poll_dynamic_once(self) -> None:
        if not self.settings.dynamic_enabled:
            return

        uids = self.store.list_uids()
        self.store.prune_dynamic_offsets(uids)
        if not uids:
            return

        channel = await self._resolve_notify_channel()
        if channel is None:
            return

        for index, uid in enumerate(uids):
            await self._process_dynamic_uid(uid, channel)
            if index < len(uids) - 1 and self.settings.dynamic_request_gap_seconds > 0:
                await asyncio.sleep(self.settings.dynamic_request_gap_seconds)

    async def _process_dynamic_uid(self, uid: str, channel: discord.abc.Messageable) -> None:
        try:
            dynamics = await self.dynamic_client.fetch_user_dynamics(uid)
        except DynamicFetchError as exc:
            logger.warning("Failed to fetch dynamics for uid {}: {}", uid, exc)
            return
        except Exception:
            logger.exception("Unexpected error while fetching dynamics for uid {}", uid)
            return

        if not dynamics:
            return

        latest_dyn_id = max(item.dyn_id for item in dynamics)
        offset = self.store.get_dynamic_offset(uid)
        if offset is None:
            self.store.upsert_dynamic_offset(uid, latest_dyn_id)
            return

        new_items = sorted((item for item in dynamics if item.dyn_id > offset), key=lambda item: item.dyn_id)
        if not new_items:
            return

        sent_up_to = offset
        now = datetime.now(timezone.utc)
        for item in new_items:
            try:
                embed, file = await self._build_dynamic_message(item, now)
                if file is not None:
                    await channel.send(embed=embed, file=file)
                else:
                    await channel.send(embed=embed)
                sent_up_to = max(sent_up_to, item.dyn_id)
            except Exception:
                logger.exception("Failed to send dynamic notification for uid {} dyn {}", uid, item.dyn_id)

        if sent_up_to > offset:
            self.store.upsert_dynamic_offset(uid, sent_up_to)

    @poll_live_status.before_loop
    async def _before_poll(self) -> None:
        await self.wait_until_ready()

    @poll_dynamic_status.before_loop
    async def _before_dynamic_poll(self) -> None:
        await self.wait_until_ready()
