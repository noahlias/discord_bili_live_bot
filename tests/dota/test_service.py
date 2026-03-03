import pytest

from discord_live_bot.dota.models import (
    DotaHeroAsset,
    DotaItemAsset,
    DotaMatchDetail,
    DotaMatchPlayerStats,
    DotaPlayerBrief,
    DotaPlayerSummary,
    DotaRecentMatch,
)
from discord_live_bot.dota.service import DotaService


class _FakeClient:
    def __init__(self):
        self.requested_account: int | None = None
        self.requested_match: int | None = None

    @staticmethod
    def normalize_account_id(raw: str) -> int:
        if raw != "455095162":
            raise ValueError("bad account")
        return 455095162

    @staticmethod
    def parse_match_id(raw: str) -> int:
        if raw != "8713425076":
            raise ValueError("bad match")
        return 8713425076

    async def fetch_player_summary(self, account_id: int) -> DotaPlayerSummary:
        self.requested_account = account_id
        return DotaPlayerSummary(
            account_id=account_id,
            persona_name="tester",
            avatar_url="",
            profile_url="",
            rank_tier=42,
            leaderboard_rank=None,
            estimated_mmr=None,
        )

    async def fetch_recent_matches(self, account_id: int, *, limit: int) -> list[DotaRecentMatch]:
        assert limit == 3
        return [
            DotaRecentMatch(
                match_id=8713425076,
                player_slot=129,
                radiant_win=False,
                hero_id=109,
                kills=5,
                deaths=5,
                assists=6,
                gold_per_min=376,
                xp_per_min=676,
                net_worth=14910,
                duration_seconds=2664,
                start_time=1772478494,
                item_ids=(151, 1),
                neutral_item_id=1638,
            )
        ]

    async def fetch_hero_assets(self) -> dict[int, DotaHeroAsset]:
        return {
            109: DotaHeroAsset(
                hero_id=109,
                localized_name="Terrorblade",
                portrait_url="https://example.com/hero_tb.png",
                icon_url="https://example.com/hero_tb_icon.png",
            )
        }

    async def fetch_item_assets(self) -> dict[int, DotaItemAsset]:
        return {
            1: DotaItemAsset(item_id=1, display_name="Blink Dagger", image_url="https://example.com/blink.png"),
            151: DotaItemAsset(item_id=151, display_name="Sange and Yasha", image_url="https://example.com/sy.png"),
            1638: DotaItemAsset(item_id=1638, display_name="Pupil's Gift", image_url="https://example.com/neutral.png"),
        }

    async def fetch_player_brief(self, account_id: int) -> DotaPlayerBrief:
        return DotaPlayerBrief(
            account_id=account_id,
            persona_name="tester-from-brief",
            avatar_url="https://example.com/avatar.jpg",
        )

    async def fetch_match_detail(self, match_id: int, *, account_id: int | None) -> DotaMatchDetail:
        self.requested_match = match_id
        assert account_id == 455095162
        return DotaMatchDetail(
            match_id=match_id,
            duration_seconds=2664,
            start_time=1772478494,
            radiant_win=False,
            radiant_score=27,
            dire_score=62,
            game_mode=22,
            lobby_type=7,
            target_player=DotaMatchPlayerStats(
                account_id=455095162,
                persona_name="",
                player_slot=129,
                hero_id=109,
                kills=5,
                deaths=5,
                assists=6,
                gold_per_min=376,
                xp_per_min=676,
                net_worth=14910,
                item_ids=(151, 1),
                neutral_item_id=1638,
                radiant_win=False,
                level=25,
                item_slot_ids=(151, 1, None, None, None, None),
                backpack_item_ids=(None, None, None),
            ),
            players=(
                DotaMatchPlayerStats(
                    account_id=455095162,
                    persona_name="",
                    player_slot=129,
                    hero_id=109,
                    kills=5,
                    deaths=5,
                    assists=6,
                    gold_per_min=376,
                    xp_per_min=676,
                    net_worth=14910,
                    item_ids=(151, 1),
                    neutral_item_id=1638,
                    radiant_win=False,
                    level=25,
                    item_slot_ids=(151, 1, None, None, None, None),
                    backpack_item_ids=(None, None, None),
                ),
            ),
        )


@pytest.mark.asyncio
async def test_build_player_report_without_match_detail():
    service = DotaService(_FakeClient(), recent_match_limit=3)

    report = await service.build_player_report(account_raw="455095162")

    assert report.account_id == 455095162
    assert report.player.persona_name == "tester"
    assert len(report.recent_matches) == 1
    assert report.match_detail is None
    assert report.hero_assets[109].localized_name == "Terrorblade"


@pytest.mark.asyncio
async def test_build_player_report_with_match_detail():
    client = _FakeClient()
    service = DotaService(client, recent_match_limit=3)

    report = await service.build_player_report(
        account_raw="455095162",
        match_id_raw="8713425076",
    )

    assert client.requested_account == 455095162
    assert client.requested_match == 8713425076
    assert report.match_detail is not None
    assert report.match_detail.target_player is not None
    assert report.match_detail.target_player.persona_name == "tester-from-brief"
    assert report.match_detail.target_player.avatar_url == "https://example.com/avatar.jpg"


@pytest.mark.asyncio
async def test_build_player_report_rejects_bad_match_id():
    service = DotaService(_FakeClient(), recent_match_limit=3)

    with pytest.raises(ValueError):
        await service.build_player_report(account_raw="455095162", match_id_raw="bad")
