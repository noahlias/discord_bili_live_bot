import pytest

from discord_live_bot.dota.client import DotaClient


def test_normalize_account_id_supports_account_and_steam64():
    assert DotaClient.normalize_account_id("455095162") == 455095162
    assert DotaClient.normalize_account_id("76561198415360890") == 455095162


@pytest.mark.parametrize("raw", ["", "abc", "0", "-1"])
def test_normalize_account_id_rejects_invalid_values(raw: str):
    with pytest.raises(ValueError):
        DotaClient.normalize_account_id(raw)


@pytest.mark.asyncio
async def test_client_parses_player_recent_and_detail(monkeypatch: pytest.MonkeyPatch):
    client = DotaClient()

    async def fake_get_json(path: str):
        if path == "/players/455095162":
            return {
                "profile": {
                    "account_id": 455095162,
                    "personaname": "tester",
                    "avatarfull": "https://example.com/avatar.jpg",
                    "profileurl": "https://steamcommunity.com/profiles/76561198415360890/",
                },
                "rank_tier": 42,
                "leaderboard_rank": 4701,
                "mmr_estimate": {"estimate": 4200},
            }
        if path == "/players/455095162/recentMatches":
            return [
                {
                    "match_id": 8713425076,
                    "player_slot": 129,
                    "radiant_win": False,
                    "hero_id": 109,
                    "kills": 5,
                    "deaths": 5,
                    "assists": 6,
                    "gold_per_min": 376,
                    "xp_per_min": 676,
                    "net_worth": 14910,
                    "duration": 2664,
                    "start_time": 1772478494,
                    "item_0": 151,
                    "item_1": 1,
                    "item_2": 104,
                    "item_3": 29,
                    "item_4": 152,
                    "item_5": 117,
                    "item_neutral": 1638,
                    "backpack_0": 0,
                    "backpack_1": 0,
                    "backpack_2": 0,
                }
            ]
        if path == "/constants/heroes":
            return {
                "109": {
                    "id": 109,
                    "localized_name": "Terrorblade",
                    "img": "/apps/dota2/images/dota_react/heroes/terrorblade.png",
                    "icon": "/apps/dota2/images/dota_react/heroes/icons/terrorblade.png",
                }
            }
        if path == "/constants/items":
            return {
                "blink": {"id": 1, "dname": "Blink Dagger", "img": "/apps/dota2/images/dota_react/items/blink.png"},
                "manta": {"id": 147, "dname": "Manta Style", "img": "/apps/dota2/images/dota_react/items/manta.png"},
            }
        if path == "/matches/8713425076":
            return {
                "match_id": 8713425076,
                "duration": 2664,
                "start_time": 1772478494,
                "radiant_win": False,
                "radiant_score": 27,
                "dire_score": 62,
                "game_mode": 22,
                "lobby_type": 7,
                "players": [
                    {
                        "account_id": 455095162,
                        "personaname": "tester",
                        "player_slot": 129,
                        "hero_id": 109,
                        "kills": 5,
                        "deaths": 5,
                        "assists": 6,
                        "gold_per_min": 376,
                        "xp_per_min": 676,
                        "net_worth": 14910,
                        "item_0": 151,
                        "item_1": 1,
                        "item_2": 104,
                        "item_3": 29,
                        "item_4": 152,
                        "item_5": 117,
                        "item_neutral": 1638,
                        "backpack_0": 0,
                        "backpack_1": 0,
                        "backpack_2": 0,
                        "level": 25,
                    }
                ],
            }
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(client, "_get_json", fake_get_json)

    player = await client.fetch_player_summary(455095162)
    assert player.persona_name == "tester"
    assert player.rank_tier == 42
    assert player.estimated_mmr == 4200

    matches = await client.fetch_recent_matches(455095162, limit=5)
    assert len(matches) == 1
    assert matches[0].won is True
    assert matches[0].item_ids == (151, 1, 104, 29, 152, 117)
    assert matches[0].item_slot_ids[:2] == (151, 1)

    detail = await client.fetch_match_detail(8713425076, account_id=455095162)
    assert detail.target_player is not None
    assert detail.target_player.hero_id == 109
    assert detail.target_player.won is True
    assert len(detail.players) == 1
    assert detail.players[0].level == 25

    heroes = await client.fetch_hero_names()
    items = await client.fetch_item_names()
    assert heroes[109] == "Terrorblade"
    assert items[1] == "Blink Dagger"
