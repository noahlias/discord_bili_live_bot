from __future__ import annotations

import io
from typing import TYPE_CHECKING, Mapping, Sequence

import discord
from loguru import logger

from ..rendering import error_embed
from .match_table import render_match_table_png
from .models import DotaRecentMatch
from .rendering import match_detail_embed

if TYPE_CHECKING:
    from ..bot import BiliDiscordBot


def _short_duration(duration_seconds: int) -> str:
    total = max(0, int(duration_seconds))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _trim_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return text[:max_len]
    return f"{text[: max_len - 1]}…"


class RecentMatchesSelect(discord.ui.Select):
    def __init__(
        self,
        *,
        account_id: int,
        matches: Sequence[DotaRecentMatch],
        hero_names: Mapping[int, str],
    ) -> None:
        options: list[discord.SelectOption] = []
        for index, match in enumerate(matches[:25], start=1):
            hero_name = hero_names.get(match.hero_id, f"Hero #{match.hero_id}")
            label = _trim_text(f"#{index} {'W' if match.won else 'L'} {hero_name}", 100)
            description = _trim_text(
                f"KDA {match.kills}/{match.deaths}/{match.assists} | {_short_duration(match.duration_seconds)} | {match.match_id}",
                100,
            )
            options.append(
                discord.SelectOption(
                    label=label,
                    description=description,
                    value=str(match.match_id),
                )
            )

        super().__init__(
            placeholder="Select a match for detail / 选择比赛查看详情",
            min_values=1,
            max_values=1,
            options=options,
        )
        self._account_id = account_id

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, RecentMatchesView):
            await interaction.response.send_message(
                embed=error_embed("Match selector is unavailable."),
                ephemeral=True,
            )
            return

        try:
            match_id = int(self.values[0])
        except (TypeError, ValueError):
            await interaction.response.send_message(
                embed=error_embed("Invalid match selection."),
                ephemeral=True,
            )
            return

        await view.handle_match_selection(
            interaction,
            account_id=self._account_id,
            match_id=match_id,
        )


class RecentMatchesView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: "BiliDiscordBot",
        account_id: int,
        matches: Sequence[DotaRecentMatch],
        hero_names: Mapping[int, str],
        timeout: float = 900,
    ) -> None:
        super().__init__(timeout=timeout)
        self._bot = bot
        self.add_item(
            RecentMatchesSelect(
                account_id=account_id,
                matches=matches,
                hero_names=hero_names,
            )
        )

    async def handle_match_selection(
        self,
        interaction: discord.Interaction,
        *,
        account_id: int,
        match_id: int,
    ) -> None:
        await interaction.response.defer(thinking=True)

        try:
            report = await self._bot.dota_service.build_player_report(
                account_raw=str(account_id),
                match_id_raw=str(match_id),
            )
        except ValueError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return
        except Exception as exc:
            logger.warning("Failed to load selected Dota match detail account={} match={}: {}", account_id, match_id, exc)
            await interaction.followup.send(
                embed=error_embed(f"Failed to fetch match detail: {exc}"),
                ephemeral=True,
            )
            return

        self._bot.store.record_dota_search(str(report.account_id), report.player.persona_name)

        if report.match_detail is None:
            await interaction.followup.send(
                embed=error_embed("Match detail is unavailable for the selected item."),
                ephemeral=True,
            )
            return

        embed = match_detail_embed(
            report.match_detail,
            hero_names=report.hero_names,
            item_names=report.item_names,
        )
        image_bytes = await render_match_table_png(
            report.match_detail,
            hero_assets=report.hero_assets,
            item_assets=report.item_assets,
        )
        if image_bytes:
            file_name = f"dota_match_{report.match_detail.match_id}.jpg"
            attachment = discord.File(io.BytesIO(image_bytes), filename=file_name)
            embed.set_image(url=f"attachment://{file_name}")
            await interaction.followup.send(embed=embed, file=attachment)
            return

        await interaction.followup.send(embed=embed)
