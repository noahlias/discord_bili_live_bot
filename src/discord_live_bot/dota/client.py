from __future__ import annotations

from typing import Any

import httpx

from .models import (
    DotaHeroAsset,
    DotaItemAsset,
    DotaMatchDetail,
    DotaMatchPlayerStats,
    DotaPlayerBrief,
    DotaPlayerSummary,
    DotaRecentMatch,
)


STEAM_ID64_BASE = 76_561_197_960_265_728


class DotaApiError(RuntimeError):
    """Raised when OpenDota API calls fail."""


class DotaClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        base_url: str = "https://api.opendota.com/api",
    ) -> None:
        self._timeout_seconds = max(1.0, float(timeout_seconds))
        self._base_url = base_url.rstrip("/")
        self._asset_base_url = "https://cdn.cloudflare.steamstatic.com"
        self._hero_names_cache: dict[int, str] | None = None
        self._item_names_cache: dict[int, str] | None = None
        self._hero_assets_cache: dict[int, DotaHeroAsset] | None = None
        self._item_assets_cache: dict[int, DotaItemAsset] | None = None
        self._player_brief_cache: dict[int, DotaPlayerBrief] = {}

    @staticmethod
    def normalize_account_id(raw: str) -> int:
        text = raw.strip()
        if not text.isdigit():
            raise ValueError("account must be numeric")

        numeric_id = int(text)
        if numeric_id <= 0:
            raise ValueError("account must be greater than 0")

        if numeric_id >= STEAM_ID64_BASE:
            numeric_id -= STEAM_ID64_BASE
            if numeric_id <= 0:
                raise ValueError("steam id conversion produced an invalid account_id")

        return numeric_id

    @staticmethod
    def parse_match_id(raw: str) -> int:
        text = raw.strip()
        if not text.isdigit():
            raise ValueError("match_id must be numeric")
        match_id = int(text)
        if match_id <= 0:
            raise ValueError("match_id must be greater than 0")
        return match_id

    async def fetch_player_summary(self, account_id: int) -> DotaPlayerSummary:
        body = await self._get_json(f"/players/{account_id}")
        if not isinstance(body, dict):
            raise DotaApiError("OpenDota player payload is invalid")

        profile = body.get("profile")
        if not isinstance(profile, dict):
            profile = {}

        mmr_estimate = body.get("mmr_estimate")
        estimate_value: int | None = None
        if isinstance(mmr_estimate, dict):
            estimate_value = self._to_optional_int(mmr_estimate.get("estimate"))

        return DotaPlayerSummary(
            account_id=self._to_optional_int(profile.get("account_id")) or account_id,
            persona_name=self._to_text(profile.get("personaname")) or str(account_id),
            avatar_url=self._to_text(profile.get("avatarfull")),
            profile_url=self._to_text(profile.get("profileurl")),
            rank_tier=self._to_optional_int(body.get("rank_tier")),
            leaderboard_rank=self._to_optional_int(body.get("leaderboard_rank")),
            estimated_mmr=estimate_value,
        )

    async def fetch_player_brief(self, account_id: int) -> DotaPlayerBrief:
        cached = self._player_brief_cache.get(account_id)
        if cached is not None:
            return cached

        summary = await self.fetch_player_summary(account_id)
        brief = DotaPlayerBrief(
            account_id=summary.account_id,
            persona_name=summary.persona_name,
            avatar_url=summary.avatar_url,
        )
        self._player_brief_cache[account_id] = brief
        return brief

    async def fetch_recent_matches(self, account_id: int, *, limit: int) -> list[DotaRecentMatch]:
        safe_limit = max(1, min(int(limit), 10))
        body = await self._get_json(f"/players/{account_id}/recentMatches")
        if not isinstance(body, list):
            raise DotaApiError("OpenDota recent matches payload is invalid")

        matches: list[DotaRecentMatch] = []
        for raw in body[:safe_limit]:
            if not isinstance(raw, dict):
                continue
            match_id = self._to_optional_int(raw.get("match_id"))
            if match_id is None:
                continue

            item_slot_ids = (
                self._to_optional_positive_int(raw.get("item_0")),
                self._to_optional_positive_int(raw.get("item_1")),
                self._to_optional_positive_int(raw.get("item_2")),
                self._to_optional_positive_int(raw.get("item_3")),
                self._to_optional_positive_int(raw.get("item_4")),
                self._to_optional_positive_int(raw.get("item_5")),
            )
            item_ids = tuple(
                item_id
                for item_id in item_slot_ids
                if item_id is not None
            )
            backpack_item_ids = (
                self._to_optional_positive_int(raw.get("backpack_0")),
                self._to_optional_positive_int(raw.get("backpack_1")),
                self._to_optional_positive_int(raw.get("backpack_2")),
            )
            matches.append(
                DotaRecentMatch(
                    match_id=match_id,
                    player_slot=self._to_int(raw.get("player_slot")),
                    radiant_win=bool(raw.get("radiant_win")),
                    hero_id=self._to_int(raw.get("hero_id")),
                    kills=self._to_int(raw.get("kills")),
                    deaths=self._to_int(raw.get("deaths")),
                    assists=self._to_int(raw.get("assists")),
                    gold_per_min=self._to_int(raw.get("gold_per_min")),
                    xp_per_min=self._to_int(raw.get("xp_per_min")),
                    net_worth=self._to_optional_int(raw.get("net_worth")),
                    duration_seconds=self._to_int(raw.get("duration")),
                    start_time=self._to_int(raw.get("start_time")),
                    item_ids=item_ids,
                    neutral_item_id=self._to_optional_positive_int(raw.get("item_neutral")),
                    item_slot_ids=item_slot_ids,
                    backpack_item_ids=backpack_item_ids,
                )
            )

        return matches

    async def fetch_match_detail(
        self,
        match_id: int,
        *,
        account_id: int | None,
    ) -> DotaMatchDetail:
        body = await self._get_json(f"/matches/{match_id}")
        if not isinstance(body, dict):
            raise DotaApiError("OpenDota match payload is invalid")

        players = body.get("players")
        if not isinstance(players, list):
            players = []

        target_player: DotaMatchPlayerStats | None = None
        if account_id is not None:
            for raw_player in players:
                if not isinstance(raw_player, dict):
                    continue
                player_account_id = self._to_optional_int(raw_player.get("account_id"))
                if player_account_id == account_id:
                    target_player = self._parse_match_player(raw_player, bool(body.get("radiant_win")))
                    break

        parsed_players = tuple(
            self._parse_match_player(raw_player, bool(body.get("radiant_win")))
            for raw_player in players
            if isinstance(raw_player, dict)
        )

        return DotaMatchDetail(
            match_id=self._to_optional_int(body.get("match_id")) or match_id,
            duration_seconds=self._to_int(body.get("duration")),
            start_time=self._to_int(body.get("start_time")),
            radiant_win=self._to_optional_bool(body.get("radiant_win")),
            radiant_score=self._to_optional_int(body.get("radiant_score")),
            dire_score=self._to_optional_int(body.get("dire_score")),
            game_mode=self._to_optional_int(body.get("game_mode")),
            lobby_type=self._to_optional_int(body.get("lobby_type")),
            target_player=target_player,
            players=parsed_players,
        )

    async def fetch_hero_assets(self) -> dict[int, DotaHeroAsset]:
        if self._hero_assets_cache is not None:
            return dict(self._hero_assets_cache)

        body = await self._get_json("/constants/heroes")
        if not isinstance(body, dict):
            raise DotaApiError("OpenDota hero constants payload is invalid")

        hero_assets: dict[int, DotaHeroAsset] = {}
        for value in body.values():
            if not isinstance(value, dict):
                continue
            hero_id = self._to_optional_int(value.get("id"))
            if hero_id is None:
                continue
            localized_name = self._to_text(value.get("localized_name")) or f"Hero #{hero_id}"
            portrait_url = self._asset_url(value.get("img"))
            icon_url = self._asset_url(value.get("icon"))
            hero_assets[hero_id] = DotaHeroAsset(
                hero_id=hero_id,
                localized_name=localized_name,
                portrait_url=portrait_url,
                icon_url=icon_url,
            )

        self._hero_assets_cache = hero_assets
        self._hero_names_cache = {hero_id: asset.localized_name for hero_id, asset in hero_assets.items()}
        return dict(hero_assets)

    async def fetch_item_assets(self) -> dict[int, DotaItemAsset]:
        if self._item_assets_cache is not None:
            return dict(self._item_assets_cache)

        body = await self._get_json("/constants/items")
        if not isinstance(body, dict):
            raise DotaApiError("OpenDota item constants payload is invalid")

        item_assets: dict[int, DotaItemAsset] = {}
        for value in body.values():
            if not isinstance(value, dict):
                continue
            item_id = self._to_optional_int(value.get("id"))
            if item_id is None:
                continue
            item_name = self._to_text(value.get("dname")) or self._to_text(value.get("name"))
            if not item_name:
                item_name = f"Item {item_id}"
            image_url = self._asset_url(value.get("img"))
            item_assets[item_id] = DotaItemAsset(
                item_id=item_id,
                display_name=item_name,
                image_url=image_url,
            )

        self._item_assets_cache = item_assets
        self._item_names_cache = {item_id: asset.display_name for item_id, asset in item_assets.items()}
        return dict(item_assets)

    async def fetch_hero_names(self) -> dict[int, str]:
        if self._hero_names_cache is not None:
            return dict(self._hero_names_cache)
        assets = await self.fetch_hero_assets()
        return {hero_id: asset.localized_name for hero_id, asset in assets.items()}

    async def fetch_item_names(self) -> dict[int, str]:
        if self._item_names_cache is not None:
            return dict(self._item_names_cache)
        assets = await self.fetch_item_assets()
        return {item_id: asset.display_name for item_id, asset in assets.items()}

    async def _get_json(self, path: str) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(url, headers={"User-Agent": "discord-live-bot/0.1"})
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DotaApiError(f"OpenDota API returned {exc.response.status_code} for {path}") from exc
        except httpx.HTTPError as exc:
            raise DotaApiError(f"OpenDota request failed: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise DotaApiError("OpenDota API returned invalid JSON") from exc

    def _parse_match_player(self, raw_player: dict[str, Any], radiant_win: bool) -> DotaMatchPlayerStats:
        item_slot_ids = (
            self._to_optional_positive_int(raw_player.get("item_0")),
            self._to_optional_positive_int(raw_player.get("item_1")),
            self._to_optional_positive_int(raw_player.get("item_2")),
            self._to_optional_positive_int(raw_player.get("item_3")),
            self._to_optional_positive_int(raw_player.get("item_4")),
            self._to_optional_positive_int(raw_player.get("item_5")),
        )
        item_ids = tuple(
            item_id
            for item_id in item_slot_ids
            if item_id is not None
        )
        backpack_item_ids = (
            self._to_optional_positive_int(raw_player.get("backpack_0")),
            self._to_optional_positive_int(raw_player.get("backpack_1")),
            self._to_optional_positive_int(raw_player.get("backpack_2")),
        )
        return DotaMatchPlayerStats(
            account_id=self._to_optional_int(raw_player.get("account_id")),
            persona_name=self._to_text(raw_player.get("personaname")),
            player_slot=self._to_int(raw_player.get("player_slot")),
            hero_id=self._to_int(raw_player.get("hero_id")),
            kills=self._to_int(raw_player.get("kills")),
            deaths=self._to_int(raw_player.get("deaths")),
            assists=self._to_int(raw_player.get("assists")),
            gold_per_min=self._to_int(raw_player.get("gold_per_min")),
            xp_per_min=self._to_int(raw_player.get("xp_per_min")),
            net_worth=self._to_optional_int(raw_player.get("net_worth")),
            item_ids=item_ids,
            neutral_item_id=self._to_optional_positive_int(raw_player.get("item_neutral")),
            radiant_win=radiant_win,
            level=self._to_int(raw_player.get("level")),
            avatar_url=self._to_text(raw_player.get("avatarfull")),
            item_slot_ids=item_slot_ids,
            backpack_item_ids=backpack_item_ids,
        )

    @staticmethod
    def _to_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_optional_positive_int(value: Any) -> int | None:
        parsed = DotaClient._to_optional_int(value)
        if parsed is None or parsed <= 0:
            return None
        return parsed

    def _asset_url(self, raw: Any) -> str:
        value = self._to_text(raw)
        if not value:
            return ""
        if value.startswith("https://") or value.startswith("http://"):
            return value
        if value.startswith("/"):
            return f"{self._asset_base_url}{value}"
        return ""

    @staticmethod
    def _to_optional_bool(value: Any) -> bool | None:
        if value is None:
            return None
        return bool(value)
