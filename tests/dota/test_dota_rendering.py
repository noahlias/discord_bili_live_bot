from discord_live_bot.dota.models import (
    DotaMatchDetail,
    DotaMatchPlayerStats,
    DotaPlayerSummary,
    DotaRecentMatch,
)
from discord_live_bot.dota.rendering import (
    match_detail_embed,
    player_summary_embed,
    recent_match_embeds,
)


def test_player_summary_embed_shape():
    player = DotaPlayerSummary(
        account_id=455095162,
        persona_name="tester",
        avatar_url="https://example.com/avatar.png",
        profile_url="https://steamcommunity.com/profiles/76561198415360890/",
        rank_tier=42,
        leaderboard_rank=4701,
        estimated_mmr=4200,
    )

    embed = player_summary_embed(player, account_id=455095162, recent_count=5)

    assert "Dota2 Player" in embed.title
    assert embed.fields[0].value == "455095162"
    assert embed.thumbnail.url == "https://example.com/avatar.png"


def test_recent_match_embeds_render_table_card():
    match = DotaRecentMatch(
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

    embeds = recent_match_embeds(
        [match],
        hero_names={109: "Terrorblade"},
        item_names={1: "Blink Dagger", 151: "Sange and Yasha", 1638: "Pupil's Gift"},
    )

    assert len(embeds) == 1
    assert embeds[0].title == "Recent Matches Table (1)"
    assert "Terrorblade" in embeds[0].description
    assert "5/5/6" in embeds[0].description
    assert "Match 8713425076" in embeds[0].fields[0].value


def test_match_detail_embed_contains_player_stats():
    detail = DotaMatchDetail(
        match_id=8713425076,
        duration_seconds=2664,
        start_time=1772478494,
        radiant_win=False,
        radiant_score=27,
        dire_score=62,
        game_mode=22,
        lobby_type=7,
        target_player=DotaMatchPlayerStats(
            account_id=455095162,
            persona_name="tester",
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
        ),
    )

    embed = match_detail_embed(
        detail,
        hero_names={109: "Terrorblade"},
        item_names={1: "Blink Dagger", 151: "Sange and Yasha", 1638: "Pupil's Gift"},
    )

    assert embed.title.endswith("8713425076")
    assert embed.fields[0].value == "WIN"
    assert embed.fields[4].value == "Terrorblade"
