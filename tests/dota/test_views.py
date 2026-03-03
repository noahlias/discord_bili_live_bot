from __future__ import annotations

from discord_live_bot.dota.models import DotaRecentMatch
from discord_live_bot.dota.views import RecentMatchesView


class _DummyService:
    async def build_player_report(self, *, account_raw: str, match_id_raw: str | None):
        raise RuntimeError("not used")


class _DummyStore:
    def record_dota_search(self, account_id: str, persona_name: str) -> None:
        del account_id, persona_name


class _DummyBot:
    def __init__(self) -> None:
        self.dota_service = _DummyService()
        self.store = _DummyStore()


def test_recent_matches_view_builds_select_options():
    view = RecentMatchesView(
        bot=_DummyBot(),
        account_id=455095162,
        matches=(
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
            ),
        ),
        hero_names={109: "Terrorblade"},
    )

    assert len(view.children) == 1
    select = view.children[0]
    assert hasattr(select, "options")
    option = select.options[0]
    assert option.value == "8713425076"
    assert "Terrorblade" in option.label
