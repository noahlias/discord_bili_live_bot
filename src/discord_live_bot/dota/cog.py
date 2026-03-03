from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from ..rendering import error_embed
from .client import DotaApiError
from .match_table import render_match_table_png, render_recent_matches_png
from .models import DotaPlayerReport
from .rendering import match_detail_embed, player_summary_embed, recent_match_embeds
from .views import RecentMatchesView

if TYPE_CHECKING:
    from ..bot import BiliDiscordBot


class DotaCog(commands.Cog):
    def __init__(self, bot: "BiliDiscordBot") -> None:
        self.bot = bot

    @app_commands.command(
        name="dota_player",
        description="Search Dota2 player recent matches",
    )
    @app_commands.describe(
        account="OpenDota account_id or Steam64",
        match_id="Optional match id for detailed stats",
    )
    async def dota_player(
        self,
        interaction: discord.Interaction,
        account: str,
        match_id: str | None = None,
    ) -> None:
        await interaction.response.defer(thinking=True)

        try:
            report = await self.bot.dota_service.build_player_report(
                account_raw=account,
                match_id_raw=match_id,
            )
        except ValueError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)))
            return
        except DotaApiError as exc:
            logger.warning("OpenDota request failed for /dota_player account={}: {}", account, exc)
            await interaction.followup.send(embed=error_embed(f"OpenDota request failed: {exc}"))
            return
        except Exception:
            logger.exception("Unexpected /dota_player error for account {}", account)
            await interaction.followup.send(embed=error_embed("Unexpected Dota2 query error."))
            return

        self.bot.store.record_dota_search(str(report.account_id), report.player.persona_name)

        embeds = self._build_player_embeds(report)
        for embed in embeds:
            await interaction.followup.send(embed=embed)

        await self._send_recent_matches(interaction, report)

        if match_id is None and report.recent_matches:
            await self._send_recent_match_selector(interaction, report)

        if report.match_detail is not None:
            await self._send_match_detail(interaction, report)

    @dota_player.autocomplete("account")
    async def dota_player_account_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        del interaction
        return self._autocomplete_account_choices(current)

    def _build_player_embeds(self, report: DotaPlayerReport) -> list[discord.Embed]:
        embeds: list[discord.Embed] = [
            player_summary_embed(
                report.player,
                account_id=report.account_id,
                recent_count=len(report.recent_matches),
            )
        ]

        if report.recent_matches:
            return embeds
        else:
            embeds.append(
                discord.Embed(
                    title="No recent matches",
                    description="OpenDota returned no recent matches for this account.",
                    color=discord.Color.blurple(),
                    timestamp=datetime.now(timezone.utc),
                )
            )

        return embeds

    async def _send_recent_matches(
        self,
        interaction: discord.Interaction,
        report: DotaPlayerReport,
    ) -> None:
        if not report.recent_matches:
            return

        image_bytes = await render_recent_matches_png(
            report.account_id,
            limit=len(report.recent_matches),
        )
        if image_bytes:
            embed = discord.Embed(
                title=f"Recent Matches ({len(report.recent_matches)})",
                description="OpenDota player matches layout",
                color=discord.Color.blurple(),
                timestamp=datetime.now(timezone.utc),
                url=f"https://www.opendota.com/players/{report.account_id}/matches",
            )
            file_name = f"dota_recent_{report.account_id}.jpg"
            attachment = discord.File(io.BytesIO(image_bytes), filename=file_name)
            embed.set_image(url=f"attachment://{file_name}")
            await interaction.followup.send(embed=embed, file=attachment)
            return

        for embed in recent_match_embeds(
            report.recent_matches,
            hero_names=report.hero_names,
            item_names=report.item_names,
        ):
            await interaction.followup.send(embed=embed)

    async def _send_match_detail(
        self,
        interaction: discord.Interaction,
        report: DotaPlayerReport,
    ) -> None:
        if report.match_detail is None:
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

    async def _send_recent_match_selector(
        self,
        interaction: discord.Interaction,
        report: DotaPlayerReport,
    ) -> None:
        view = RecentMatchesView(
            bot=self.bot,
            account_id=report.account_id,
            matches=report.recent_matches,
            hero_names=report.hero_names,
        )
        embed = discord.Embed(
            title="Pick Match Detail",
            description="Choose a recent match below to open detail. No need to remember match_id.",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        await interaction.followup.send(embed=embed, view=view)

    def _autocomplete_account_choices(self, current: str) -> list[app_commands.Choice[str]]:
        rows = self.bot.store.list_dota_searches(current, limit=25)
        choices: list[app_commands.Choice[str]] = []
        for account_id, persona_name, search_count in rows:
            if persona_name:
                label = f"{persona_name} ({account_id}) · {search_count}"
            else:
                label = f"{account_id} · {search_count}"
            if len(label) > 100:
                label = f"{label[:97]}..."
            choices.append(app_commands.Choice(name=label, value=account_id))
        return choices
