from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Sequence

import discord

from .models import DotaMatchDetail, DotaMatchPlayerStats, DotaPlayerSummary, DotaRecentMatch


SUMMARY_COLOR = discord.Color.orange()
DETAIL_COLOR = discord.Color.blurple()


def _format_duration(duration_seconds: int) -> str:
    total = max(0, int(duration_seconds))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _hero_name(hero_id: int, hero_names: Mapping[int, str]) -> str:
    return hero_names.get(hero_id, f"Hero #{hero_id}")


def _item_name(item_id: int, item_names: Mapping[int, str]) -> str:
    return item_names.get(item_id, f"Item #{item_id}")


def _format_item_list(
    *,
    item_ids: Sequence[int],
    neutral_item_id: int | None,
    item_names: Mapping[int, str],
) -> str:
    listed = [_item_name(item_id, item_names) for item_id in item_ids]
    if neutral_item_id is not None and neutral_item_id > 0:
        listed.append(f"Neutral: {_item_name(neutral_item_id, item_names)}")
    if not listed:
        return "None"
    return " | ".join(listed)


def _rank_text(player: DotaPlayerSummary) -> str:
    if player.rank_tier is None:
        return "Unknown"
    medal = player.rank_tier // 10
    stars = player.rank_tier % 10
    text = f"Tier {player.rank_tier} (medal {medal}, star {stars})"
    if player.leaderboard_rank is not None:
        text = f"{text}, leaderboard #{player.leaderboard_rank}"
    return text


def _trim_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return text[:max_len]
    return f"{text[: max_len - 1]}…"


def _compact_duration(duration_seconds: int) -> str:
    total = max(0, int(duration_seconds))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def player_summary_embed(
    player: DotaPlayerSummary,
    *,
    account_id: int,
    recent_count: int,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Dota2 Player: {player.persona_name}",
        color=SUMMARY_COLOR,
        timestamp=datetime.now(timezone.utc),
    )
    embed.description = "Recent match summary from OpenDota"
    embed.add_field(name="Account ID", value=str(account_id), inline=True)
    if player.profile_url:
        embed.add_field(name="Profile", value=f"[Open Steam Profile]({player.profile_url})", inline=True)
    else:
        embed.add_field(name="Profile", value="Unavailable", inline=True)
    embed.add_field(name="Rank", value=_rank_text(player), inline=False)
    if player.estimated_mmr is not None:
        embed.add_field(name="Estimated MMR", value=str(player.estimated_mmr), inline=True)
    embed.add_field(name="Recent Matches Shown", value=str(recent_count), inline=True)
    if player.avatar_url:
        embed.set_thumbnail(url=player.avatar_url)
    embed.set_footer(text="OpenDota / Search mode")
    return embed


def recent_match_embeds(
    matches: Sequence[DotaRecentMatch],
    *,
    hero_names: Mapping[int, str],
    item_names: Mapping[int, str],
) -> list[discord.Embed]:
    del item_names
    if not matches:
        return []

    header = f"{'#':>2} {'R':>1} {'Hero':<14} {'K/D/A':<11} {'Dur':<8} {'Match'}"
    rows = [header]
    links: list[str] = []
    for index, match in enumerate(matches, start=1):
        result = "W" if match.won else "L"
        hero_text = _trim_text(_hero_name(match.hero_id, hero_names), 14)
        kda_text = f"{match.kills}/{match.deaths}/{match.assists}"
        duration_text = _compact_duration(match.duration_seconds)
        rows.append(f"{index:>2} {result:>1} {hero_text:<14} {kda_text:<11} {duration_text:<8} {match.match_id}")
        links.append(f"`{index:>2}` [Match {match.match_id}](https://www.opendota.com/matches/{match.match_id})")

    embed = discord.Embed(
        title=f"Recent Matches Table ({len(matches)})",
        color=SUMMARY_COLOR,
        timestamp=datetime.now(timezone.utc),
        description="```text\n" + "\n".join(rows) + "\n```",
    )
    embed.add_field(name="OpenDota Links", value="\n".join(links), inline=False)
    embed.add_field(
        name="Columns",
        value="`R`: W/L result, `Dur`: duration",
        inline=False,
    )
    return [embed]


def _match_result_text(detail: DotaMatchDetail, player: DotaMatchPlayerStats | None) -> str:
    if detail.radiant_win is None:
        return "Unknown"
    if player is None:
        return "Radiant Win" if detail.radiant_win else "Dire Win"
    return "WIN" if player.won else "LOSE"


def match_detail_embed(
    detail: DotaMatchDetail,
    *,
    hero_names: Mapping[int, str],
    item_names: Mapping[int, str],
) -> discord.Embed:
    player = detail.target_player
    result_text = _match_result_text(detail, player)
    embed = discord.Embed(
        title=f"Match Detail: {detail.match_id}",
        color=DETAIL_COLOR,
        timestamp=datetime.now(timezone.utc),
        url=f"https://www.opendota.com/matches/{detail.match_id}",
    )
    embed.add_field(name="Result", value=result_text, inline=True)
    embed.add_field(name="Duration", value=_format_duration(detail.duration_seconds), inline=True)
    embed.add_field(name="Start", value=f"<t:{detail.start_time}:F>", inline=False)

    if detail.radiant_score is not None and detail.dire_score is not None:
        embed.add_field(
            name="Score",
            value=f"Radiant {detail.radiant_score} : {detail.dire_score} Dire",
            inline=False,
        )

    if player is None:
        embed.description = "Player row was not found in this match payload."
        return embed

    hero_name = _hero_name(player.hero_id, hero_names)
    embed.add_field(name="Hero", value=hero_name, inline=True)
    embed.add_field(name="K / D / A", value=f"{player.kills} / {player.deaths} / {player.assists}", inline=True)
    player_name = player.persona_name or str(player.account_id or "unknown")
    embed.add_field(name="Player", value=player_name, inline=True)

    economy_text = f"GPM {player.gold_per_min} | XPM {player.xp_per_min}"
    if player.net_worth is not None:
        economy_text = f"{economy_text} | NW {player.net_worth}"
    embed.add_field(name="Economy", value=economy_text, inline=False)
    embed.add_field(
        name="Items",
        value=_format_item_list(
            item_ids=player.item_ids,
            neutral_item_id=player.neutral_item_id,
            item_names=item_names,
        ),
        inline=False,
    )

    return embed
