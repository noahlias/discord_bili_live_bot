from __future__ import annotations

import pytest

from discord_live_bot.bili_client import BiliClient
from discord_live_bot.bot import BiliDiscordBot
from discord_live_bot.config import Settings
from discord_live_bot.db import SubscriptionStore
from discord_live_bot.dynamic_client import DynamicFetchError, DynamicItem
from discord_live_bot.status_tracker import StatusTracker


class _DummyChannel:
    def __init__(self) -> None:
        self.embeds = []
        self.files = []

    async def send(self, *, embed=None, view=None, file=None):
        del view
        self.embeds.append(embed)
        self.files.append(file)


class _SequenceDynamicClient:
    def __init__(self, responses: dict[str, list[list[DynamicItem]]], errors: dict[str, Exception] | None = None):
        self._responses = responses
        self._errors = errors or {}
        self._calls: dict[str, int] = {}

    async def fetch_user_dynamics(self, uid: str) -> list[DynamicItem]:
        if uid in self._errors:
            raise self._errors[uid]

        index = self._calls.get(uid, 0)
        self._calls[uid] = index + 1
        series = self._responses.get(uid, [[]])
        return list(series[min(index, len(series) - 1)])


def _settings(db_path: str, *, gap: float = 0) -> Settings:
    return Settings(
        discord_token="x",
        notify_channel_id=1,
        guild_id=None,
        bili_voice_fixed_channel_id=None,
        poll_interval_seconds=30,
        dynamic_enabled=True,
        dynamic_poll_interval_seconds=60,
        dynamic_request_gap_seconds=gap,
        dynamic_screenshot_enabled=True,
        dynamic_browser_screenshot_enabled=False,
        dynamic_browser_timeout_seconds=20,
        dynamic_browser_max_concurrency=1,
        dynamic_browser_args=("--disable-dev-shm-usage",),
        dynamic_browser_capture_url_template="https://m.bilibili.com/dynamic/{dyn_id}",
        dynamic_browser_long_screenshot_enabled=False,
        dynamic_browser_opus_fallback_enabled=True,
        dynamic_browser_opus_fallback_url_template="https://www.bilibili.com/opus/{dyn_id}",
        dynamic_browser_ua="test-ua",
        dynamic_captcha_address="",
        dynamic_captcha_token="harukabot",
        dynamic_screenshot_template="https://image.thum.io/get/width/1200/noanimate/https://t.bilibili.com/{dyn_id}",
        sqlite_path=db_path,
        log_level="INFO",
        bili_voice_enabled=True,
        bili_voice_streamlink_quality="audio_only",
        bili_voice_ffmpeg_path="",
    )


def _item(uid: str, dyn_id: int) -> DynamicItem:
    return DynamicItem(
        uid=uid,
        dyn_id=dyn_id,
        card_type=7,
        card_type_label="draw",
        author_name="tester",
        cover_url=f"https://example.com/{dyn_id}.jpg",
    )


@pytest.mark.asyncio
async def test_dynamic_poll_initializes_offset_then_pushes_new(tmp_path):
    db_path = tmp_path / "bot.db"
    store = SubscriptionStore(str(db_path))
    store.add_uid("7261854")

    dynamic_client = _SequenceDynamicClient(
        {
            "7261854": [
                [_item("7261854", 100), _item("7261854", 90)],
                [_item("7261854", 110), _item("7261854", 100)],
            ]
        }
    )

    bot = BiliDiscordBot(
        settings=_settings(str(db_path)),
        store=store,
        bili_client=BiliClient(),
        dynamic_client=dynamic_client,
        tracker=StatusTracker(),
    )
    channel = _DummyChannel()

    async def _resolve():
        return channel

    bot._resolve_notify_channel = _resolve  # type: ignore[method-assign]

    await bot._poll_dynamic_once()
    assert store.get_dynamic_offset("7261854") == 100
    assert len(channel.embeds) == 0

    await bot._poll_dynamic_once()
    assert store.get_dynamic_offset("7261854") == 110
    assert len(channel.embeds) == 1
    assert channel.embeds[0].fields[1].value == "110"
    assert channel.embeds[0].image.url == "https://example.com/110.jpg"

    await bot.close()


@pytest.mark.asyncio
async def test_dynamic_poll_skips_failed_uid_and_continues(tmp_path):
    db_path = tmp_path / "bot.db"
    store = SubscriptionStore(str(db_path))
    store.add_uid("1")
    store.add_uid("2")
    store.upsert_dynamic_offset("2", 100)

    dynamic_client = _SequenceDynamicClient(
        {"2": [[_item("2", 110)]]},
        errors={"1": DynamicFetchError("boom")},
    )

    bot = BiliDiscordBot(
        settings=_settings(str(db_path)),
        store=store,
        bili_client=BiliClient(),
        dynamic_client=dynamic_client,
        tracker=StatusTracker(),
    )
    channel = _DummyChannel()

    async def _resolve():
        return channel

    bot._resolve_notify_channel = _resolve  # type: ignore[method-assign]

    await bot._poll_dynamic_once()

    assert len(channel.embeds) == 1
    assert store.get_dynamic_offset("2") == 110

    await bot.close()


@pytest.mark.asyncio
async def test_dynamic_poll_honors_request_gap(monkeypatch, tmp_path):
    db_path = tmp_path / "bot.db"
    store = SubscriptionStore(str(db_path))
    store.add_uid("1")
    store.add_uid("2")

    dynamic_client = _SequenceDynamicClient({"1": [[]], "2": [[]]})

    bot = BiliDiscordBot(
        settings=_settings(str(db_path), gap=0.5),
        store=store,
        bili_client=BiliClient(),
        dynamic_client=dynamic_client,
        tracker=StatusTracker(),
    )
    channel = _DummyChannel()

    async def _resolve():
        return channel

    bot._resolve_notify_channel = _resolve  # type: ignore[method-assign]

    sleep_calls: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr("discord_live_bot.bot.asyncio.sleep", _fake_sleep)

    await bot._poll_dynamic_once()

    assert sleep_calls == [0.5]

    await bot.close()


@pytest.mark.asyncio
async def test_bot_close_closes_dynamic_screenshotter(monkeypatch, tmp_path):
    db_path = tmp_path / "bot.db"
    store = SubscriptionStore(str(db_path))

    bot = BiliDiscordBot(
        settings=_settings(str(db_path)),
        store=store,
        bili_client=BiliClient(),
        dynamic_client=_SequenceDynamicClient({}),
        tracker=StatusTracker(),
    )

    closed = {"value": False}

    async def _fake_aclose() -> None:
        closed["value"] = True

    async def _fake_super_close(self) -> None:  # noqa: ARG001
        return None

    monkeypatch.setattr(bot.dynamic_screenshotter, "aclose", _fake_aclose)
    monkeypatch.setattr("discord_live_bot.bot.commands.Bot.close", _fake_super_close)

    await bot.close()

    assert closed["value"] is True
