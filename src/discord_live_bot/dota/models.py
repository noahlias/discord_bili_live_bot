from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DotaPlayerBrief:
    account_id: int
    persona_name: str
    avatar_url: str


@dataclass(frozen=True)
class DotaHeroAsset:
    hero_id: int
    localized_name: str
    portrait_url: str
    icon_url: str


@dataclass(frozen=True)
class DotaItemAsset:
    item_id: int
    display_name: str
    image_url: str


@dataclass(frozen=True)
class DotaPlayerSummary:
    account_id: int
    persona_name: str
    avatar_url: str
    profile_url: str
    rank_tier: int | None
    leaderboard_rank: int | None
    estimated_mmr: int | None


@dataclass(frozen=True)
class DotaRecentMatch:
    match_id: int
    player_slot: int
    radiant_win: bool
    hero_id: int
    kills: int
    deaths: int
    assists: int
    gold_per_min: int
    xp_per_min: int
    net_worth: int | None
    duration_seconds: int
    start_time: int
    item_ids: tuple[int, ...]
    neutral_item_id: int | None
    item_slot_ids: tuple[int | None, ...] = ()
    backpack_item_ids: tuple[int | None, ...] = ()

    @property
    def won(self) -> bool:
        is_radiant = self.player_slot < 128
        return (is_radiant and self.radiant_win) or ((not is_radiant) and (not self.radiant_win))


@dataclass(frozen=True)
class DotaMatchPlayerStats:
    account_id: int | None
    persona_name: str
    player_slot: int
    hero_id: int
    kills: int
    deaths: int
    assists: int
    gold_per_min: int
    xp_per_min: int
    net_worth: int | None
    item_ids: tuple[int, ...]
    neutral_item_id: int | None
    radiant_win: bool
    level: int = 0
    avatar_url: str = ""
    item_slot_ids: tuple[int | None, ...] = ()
    backpack_item_ids: tuple[int | None, ...] = ()

    @property
    def won(self) -> bool:
        is_radiant = self.player_slot < 128
        return (is_radiant and self.radiant_win) or ((not is_radiant) and (not self.radiant_win))


@dataclass(frozen=True)
class DotaMatchDetail:
    match_id: int
    duration_seconds: int
    start_time: int
    radiant_win: bool | None
    radiant_score: int | None
    dire_score: int | None
    game_mode: int | None
    lobby_type: int | None
    target_player: DotaMatchPlayerStats | None
    players: tuple[DotaMatchPlayerStats, ...] = ()


@dataclass(frozen=True)
class DotaPlayerReport:
    account_id: int
    player: DotaPlayerSummary
    recent_matches: tuple[DotaRecentMatch, ...]
    hero_names: dict[int, str]
    item_names: dict[int, str]
    hero_assets: dict[int, DotaHeroAsset]
    item_assets: dict[int, DotaItemAsset]
    match_detail: DotaMatchDetail | None
