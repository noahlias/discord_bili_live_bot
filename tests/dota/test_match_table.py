from discord_live_bot.dota.match_table import build_match_table_html
from discord_live_bot.dota.models import DotaHeroAsset, DotaItemAsset, DotaMatchDetail, DotaMatchPlayerStats


def _player(account_id: int, *, slot: int, radiant_win: bool, name: str) -> DotaMatchPlayerStats:
    return DotaMatchPlayerStats(
        account_id=account_id,
        persona_name=name,
        player_slot=slot,
        hero_id=109,
        kills=5,
        deaths=5,
        assists=6,
        gold_per_min=376,
        xp_per_min=676,
        net_worth=14910,
        item_ids=(151, 1),
        neutral_item_id=1638,
        radiant_win=radiant_win,
        level=25,
        avatar_url="https://example.com/avatar.jpg",
        item_slot_ids=(151, 1, None, None, None, None),
        backpack_item_ids=(None, None, None),
    )


def test_build_match_table_html_contains_player_rows_and_assets():
    detail = DotaMatchDetail(
        match_id=8713425076,
        duration_seconds=2664,
        start_time=1772478494,
        radiant_win=False,
        radiant_score=27,
        dire_score=62,
        game_mode=22,
        lobby_type=7,
        target_player=None,
        players=(
            _player(1, slot=0, radiant_win=False, name="RadiantOne"),
            _player(2, slot=129, radiant_win=False, name="DireOne"),
        ),
    )

    html = build_match_table_html(
        detail,
        hero_assets={
            109: DotaHeroAsset(
                hero_id=109,
                localized_name="Terrorblade",
                portrait_url="https://example.com/hero.png",
                icon_url="https://example.com/hero_icon.png",
            )
        },
        item_assets={
            1: DotaItemAsset(item_id=1, display_name="Blink Dagger", image_url="https://example.com/blink.png"),
            151: DotaItemAsset(item_id=151, display_name="Sange and Yasha", image_url="https://example.com/sy.png"),
            1638: DotaItemAsset(item_id=1638, display_name="Pupil's Gift", image_url="https://example.com/neutral.png"),
        },
    )

    assert "RadiantOne" in html
    assert "DireOne" in html
    assert "hero_icon.png" in html
    assert "blink.png" in html
    assert "Match #8713425076" in html
