from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

import discord

from .bili_client import RoomInfo


LIVE_COLOR = discord.Color.green()
OFFLINE_COLOR = discord.Color.dark_gray()
SUMMARY_COLOR = discord.Color.blurple()
ERROR_COLOR = discord.Color.red()


def format_duration(duration_seconds: int | None) -> str:
    if duration_seconds is None or duration_seconds < 0:
        return "unknown / 未知"
    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def live_start_embed(room: RoomInfo, detected_at: datetime) -> discord.Embed:
    embed = discord.Embed(
        title=f"🔴 {room.uname} is LIVE / 开播啦",
        color=LIVE_COLOR,
        timestamp=detected_at,
    )
    embed.description = f"**Title 标题**\n{room.title or 'No title / 无标题'}"
    embed.add_field(name="Category 分区", value=f"{room.area_parent} / {room.area_name}", inline=True)
    embed.add_field(name="UID", value=room.uid, inline=True)
    embed.add_field(name="Room", value=f"[Open 打开直播间]({room.room_url})", inline=True)
    if room.face:
        embed.set_thumbnail(url=room.face)
    if room.cover:
        embed.set_image(url=room.cover)
    embed.set_footer(text="Detected by poller / 轮询检测")
    return embed


def live_start_view(room: RoomInfo) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label="Watch Live", style=discord.ButtonStyle.link, url=room.room_url))
    view.add_item(
        discord.ui.Button(
            label="Bilibili Profile",
            style=discord.ButtonStyle.link,
            url=room.profile_url,
        )
    )
    return view


def live_end_embed(room: RoomInfo, duration_seconds: int | None, detected_at: datetime) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚫ {room.uname} went offline / 下播了",
        color=OFFLINE_COLOR,
        timestamp=detected_at,
    )
    embed.add_field(name="Session Duration 本次时长", value=format_duration(duration_seconds), inline=False)
    embed.add_field(name="UID", value=room.uid, inline=True)
    embed.add_field(name="Last Room", value=f"[Open 查看直播间]({room.room_url})", inline=True)
    if room.face:
        embed.set_thumbnail(url=room.face)
    embed.set_footer(text="Status changed / 状态变更")
    return embed


def empty_state_embed() -> discord.Embed:
    embed = discord.Embed(
        title="No subscriptions yet / 还没有订阅",
        description="Use `/subscribe uid:<bilibili_uid>` to add one.",
        color=SUMMARY_COLOR,
        timestamp=datetime.now(timezone.utc),
    )
    return embed


def error_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="Error / 错误",
        description=message,
        color=ERROR_COLOR,
        timestamp=datetime.now(timezone.utc),
    )


def snapshot_embeds(
    rooms: Sequence[RoomInfo],
    following_count: int,
    *,
    live_only: bool,
    max_cards: int = 20,
) -> list[discord.Embed]:
    if max_cards <= 0:
        max_cards = 20

    sorted_rooms = sorted(
        rooms,
        key=lambda room: (
            0 if room.live_status else 1,
            room.uname.lower(),
        ),
    )
    if not sorted_rooms:
        title = "Live now / 当前开播" if live_only else "Subscriptions / 订阅列表"
        embed = discord.Embed(
            title=title,
            description="No users to display / 没有可展示的用户。",
            color=SUMMARY_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Following", value=str(following_count), inline=True)
        embed.add_field(name="Live now", value="0", inline=True)
        return [embed]

    live_count = sum(1 for room in sorted_rooms if room.live_status)
    displayed_rooms = list(sorted_rooms[:max_cards])

    title = "Live now / 当前开播" if live_only else "Subscriptions / 订阅列表"
    summary = discord.Embed(
        title=title,
        description=f"Showing {len(displayed_rooms)} user cards / 展示 {len(displayed_rooms)} 位用户卡片",
        color=SUMMARY_COLOR,
        timestamp=datetime.now(timezone.utc),
    )
    summary.add_field(name="Following", value=str(following_count), inline=True)
    summary.add_field(name="Live now", value=str(live_count), inline=True)
    summary.add_field(name="Shown", value=str(len(displayed_rooms)), inline=True)

    embeds: list[discord.Embed] = [summary]
    for idx, room in enumerate(displayed_rooms, start=1):
        is_live = bool(room.live_status)
        status_icon = "🟢" if is_live else "⚪"
        status_text = "LIVE / 开播中" if is_live else "OFFLINE / 未开播"
        color = LIVE_COLOR if is_live else OFFLINE_COLOR
        card = discord.Embed(
            title=f"{status_icon} {room.uname} - {status_text}",
            color=color,
            timestamp=datetime.now(timezone.utc),
            description=(
                f"**Title 标题**\n{room.title or 'No title / 无标题'}\n\n"
                f"**Category 分区**\n{room.area_parent} / {room.area_name}"
            ),
        )
        card.add_field(name="UID", value=room.uid, inline=True)
        card.add_field(name="Room", value=f"[Open 打开直播间]({room.room_url})", inline=True)
        card.add_field(name="Profile", value=f"[Space 主页]({room.profile_url})", inline=True)
        if room.face:
            card.set_thumbnail(url=room.face)
        if room.cover:
            card.set_image(url=room.cover)
        card.set_footer(text=f"Card {idx}/{len(displayed_rooms)}")
        embeds.append(card)

    if len(sorted_rooms) > len(displayed_rooms):
        overflow = len(sorted_rooms) - len(displayed_rooms)
        embeds.append(
            discord.Embed(
                title="More users not shown / 还有更多用户未展示",
                description=f"{overflow} more users omitted to keep message size safe.",
                color=SUMMARY_COLOR,
                timestamp=datetime.now(timezone.utc),
            )
        )

    return embeds
