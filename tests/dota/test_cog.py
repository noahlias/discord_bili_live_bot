from __future__ import annotations

import pytest

from discord_live_bot.dota.cog import DotaCog
from discord_live_bot.dota.models import DotaPlayerReport, DotaPlayerSummary, DotaRecentMatch


class _DummyResponse:
    def __init__(self) -> None:
        self.deferred = False

    async def defer(self, *, thinking: bool):
        assert thinking is True
        self.deferred = True


class _DummyFollowup:
    def __init__(self) -> None:
        self.embeds = []
        self.files = []
        self.views = []

    async def send(self, *, embed, file=None, view=None):
        self.embeds.append(embed)
        self.files.append(file)
        self.views.append(view)


class _DummyInteraction:
    def __init__(self) -> None:
        self.response = _DummyResponse()
        self.followup = _DummyFollowup()


class _DummyStore:
    def __init__(self, search_rows=None) -> None:
        self.search_rows = list(search_rows or [])
        self.recorded: list[tuple[str, str]] = []
        self.queries: list[tuple[str, int]] = []

    def record_dota_search(self, account_id: str, persona_name: str) -> None:
        self.recorded.append((account_id, persona_name))

    def list_dota_searches(self, query: str = "", *, limit: int = 25):
        self.queries.append((query, limit))
        return list(self.search_rows)


class _OkService:
    async def build_player_report(self, *, account_raw: str, match_id_raw: str | None):
        del account_raw, match_id_raw
        return DotaPlayerReport(
            account_id=455095162,
            player=DotaPlayerSummary(
                account_id=455095162,
                persona_name="tester",
                avatar_url="",
                profile_url="",
                rank_tier=42,
                leaderboard_rank=None,
                estimated_mmr=None,
            ),
            recent_matches=(
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
            hero_names={},
            item_names={},
            hero_assets={},
            item_assets={},
            match_detail=None,
        )


class _BadService:
    async def build_player_report(self, *, account_raw: str, match_id_raw: str | None):
        del account_raw, match_id_raw
        raise ValueError("account must be numeric")


class _DummyBot:
    def __init__(self, service, store: _DummyStore | None = None) -> None:
        self.dota_service = service
        self.store = store or _DummyStore()


@pytest.mark.asyncio
async def test_dota_player_command_success_sends_embeds(monkeypatch: pytest.MonkeyPatch):
    store = _DummyStore()
    cog = DotaCog(_DummyBot(_OkService(), store))
    interaction = _DummyInteraction()

    async def _fake_recent(account_id: int, limit: int):
        del account_id, limit
        return b"jpeg-bytes"

    monkeypatch.setattr("discord_live_bot.dota.cog.render_recent_matches_png", _fake_recent)
    await cog.dota_player.callback(cog, interaction, "455095162", None)

    assert interaction.response.deferred is True
    assert len(interaction.followup.embeds) == 3
    assert interaction.followup.embeds[0].fields[0].value == "455095162"
    assert interaction.followup.files[1] is not None
    assert interaction.followup.views[2] is not None
    assert store.recorded == [("455095162", "tester")]


@pytest.mark.asyncio
async def test_dota_player_command_validation_error():
    store = _DummyStore()
    cog = DotaCog(_DummyBot(_BadService(), store))
    interaction = _DummyInteraction()

    await cog.dota_player.callback(cog, interaction, "bad", None)

    assert interaction.response.deferred is True
    assert len(interaction.followup.embeds) == 1
    assert "numeric" in interaction.followup.embeds[0].description
    assert store.recorded == []


def test_dota_account_autocomplete_uses_store_frequency_results():
    store = _DummyStore(
        [
            ("455095162", "o(´^｀)o", 12),
            ("123456789", "", 2),
        ]
    )
    cog = DotaCog(_DummyBot(_OkService(), store))

    choices = cog._autocomplete_account_choices("45")

    assert store.queries == [("45", 25)]
    assert len(choices) == 2
    assert choices[0].value == "455095162"
    assert choices[0].name.startswith("o(´^｀)o (455095162)")
    assert choices[1].name == "123456789 · 2"


@pytest.mark.asyncio
async def test_dota_player_command_falls_back_when_recent_screenshot_fails(monkeypatch: pytest.MonkeyPatch):
    store = _DummyStore()
    cog = DotaCog(_DummyBot(_OkService(), store))
    interaction = _DummyInteraction()

    async def _fake_recent(account_id: int, limit: int):
        del account_id, limit
        return None

    monkeypatch.setattr("discord_live_bot.dota.cog.render_recent_matches_png", _fake_recent)

    await cog.dota_player.callback(cog, interaction, "455095162", None)

    assert len(interaction.followup.embeds) == 3
    assert interaction.followup.files[1] is None
    assert "Recent Matches Table" in interaction.followup.embeds[1].title
    assert interaction.followup.views[2] is not None
