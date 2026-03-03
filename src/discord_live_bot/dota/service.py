from __future__ import annotations

import asyncio
from dataclasses import replace

from .client import DotaClient
from .models import DotaMatchDetail, DotaPlayerReport


class DotaService:
    def __init__(self, client: DotaClient, *, recent_match_limit: int = 5) -> None:
        self._client = client
        self._recent_match_limit = max(1, min(int(recent_match_limit), 10))

    async def build_player_report(
        self,
        *,
        account_raw: str,
        match_id_raw: str | None = None,
    ) -> DotaPlayerReport:
        account_id = self._client.normalize_account_id(account_raw)

        match_id: int | None = None
        if match_id_raw:
            match_id = self._client.parse_match_id(match_id_raw)

        player_task = self._client.fetch_player_summary(account_id)
        recent_task = self._client.fetch_recent_matches(account_id, limit=self._recent_match_limit)
        hero_assets_task = self._client.fetch_hero_assets()
        item_assets_task = self._client.fetch_item_assets()

        detail_task = None
        if match_id is not None:
            detail_task = self._client.fetch_match_detail(match_id, account_id=account_id)

        if detail_task is None:
            player, recent_matches, hero_assets, item_assets = await asyncio.gather(
                player_task,
                recent_task,
                hero_assets_task,
                item_assets_task,
            )
            match_detail = None
        else:
            player, recent_matches, hero_assets, item_assets, match_detail = await asyncio.gather(
                player_task,
                recent_task,
                hero_assets_task,
                item_assets_task,
                detail_task,
            )
            match_detail = await self._enrich_match_detail_players(match_detail)

        hero_names = {hero_id: asset.localized_name for hero_id, asset in hero_assets.items()}
        item_names = {item_id: asset.display_name for item_id, asset in item_assets.items()}

        return DotaPlayerReport(
            account_id=account_id,
            player=player,
            recent_matches=tuple(recent_matches),
            hero_names=hero_names,
            item_names=item_names,
            hero_assets=hero_assets,
            item_assets=item_assets,
            match_detail=match_detail,
        )

    async def _enrich_match_detail_players(self, detail: DotaMatchDetail) -> DotaMatchDetail:
        if not detail.players:
            return detail

        account_ids = sorted(
            {
                player.account_id
                for player in detail.players
                if player.account_id is not None
            }
        )
        if not account_ids:
            return detail

        results = await asyncio.gather(
            *(self._client.fetch_player_brief(account_id) for account_id in account_ids),
            return_exceptions=True,
        )
        brief_by_account = {
            brief.account_id: brief
            for brief in results
            if not isinstance(brief, Exception)
        }

        enriched_players = []
        for player in detail.players:
            if player.account_id is None:
                enriched_players.append(player)
                continue

            brief = brief_by_account.get(player.account_id)
            if brief is None:
                enriched_players.append(player)
                continue

            updated_name = player.persona_name or brief.persona_name
            updated_avatar = player.avatar_url or brief.avatar_url
            enriched_players.append(
                replace(
                    player,
                    persona_name=updated_name,
                    avatar_url=updated_avatar,
                )
            )

        new_target = None
        if detail.target_player is not None:
            for candidate in enriched_players:
                same_account = candidate.account_id == detail.target_player.account_id
                same_slot = candidate.player_slot == detail.target_player.player_slot
                if same_account and same_slot:
                    new_target = candidate
                    break
            if new_target is None:
                new_target = detail.target_player

        return replace(
            detail,
            target_player=new_target,
            players=tuple(enriched_players),
        )
