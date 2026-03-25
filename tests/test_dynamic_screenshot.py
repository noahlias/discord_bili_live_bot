from __future__ import annotations

import asyncio
import sys
import types
from dataclasses import dataclass, field

import pytest

from discord_live_bot.config import Settings
from discord_live_bot.dynamic_screenshot import DynamicScreenshot, DynamicScreenshotter


@dataclass
class _FakeState:
    playwright_starts: int = 0
    playwright_stops: int = 0
    launch_calls: int = 0
    launch_args: list[str] = field(default_factory=list)
    new_context_calls: int = 0
    context_closes: int = 0
    browser_closes: int = 0
    active_contexts: int = 0
    max_active_contexts: int = 0
    browser_connected: bool = True
    gate_event: asyncio.Event | None = None
    first_goto_entered: asyncio.Event = field(default_factory=asyncio.Event)
    last_goto_url: str = ""
    full_page_screenshots: int = 0
    card_screenshots: int = 0


class _FakeElement:
    def __init__(self, state: _FakeState):
        self._state = state

    async def screenshot(self, *, type: str, quality: int) -> bytes:  # noqa: A002
        del type, quality
        self._state.card_screenshots += 1
        return b"card"


class _FakePage:
    def __init__(self, state: _FakeState):
        self._state = state
        self.url = "about:blank"

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        del wait_until, timeout
        self.url = url
        self._state.last_goto_url = url
        self._state.first_goto_entered.set()
        if self._state.gate_event is not None:
            await self._state.gate_event.wait()

    async def wait_for_load_state(self, state: str) -> None:
        del state

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        del timeout_ms

    async def evaluate(self, script: str) -> None:
        del script

    async def wait_for_selector(self, selector: str, *, timeout: int) -> None:
        del selector, timeout

    async def query_selector(self, selector: str):
        del selector
        return _FakeElement(self._state)

    async def screenshot(self, *, full_page: bool, type: str, quality: int) -> bytes:  # noqa: A002
        del full_page, type, quality
        self._state.full_page_screenshots += 1
        return b"full-page"


class _FakeContext:
    def __init__(self, state: _FakeState):
        self._state = state

    async def new_page(self) -> _FakePage:
        return _FakePage(self._state)

    async def close(self) -> None:
        self._state.context_closes += 1
        self._state.active_contexts -= 1


class _FakeBrowser:
    def __init__(self, state: _FakeState):
        self._state = state

    def is_connected(self) -> bool:
        return self._state.browser_connected

    async def new_context(
        self,
        *,
        user_agent: str,
        viewport: dict[str, int],
        device_scale_factor: int,
    ) -> _FakeContext:
        del user_agent, viewport, device_scale_factor
        self._state.new_context_calls += 1
        self._state.active_contexts += 1
        self._state.max_active_contexts = max(
            self._state.max_active_contexts,
            self._state.active_contexts,
        )
        return _FakeContext(self._state)

    async def close(self) -> None:
        self._state.browser_closes += 1
        self._state.browser_connected = False


class _FakeChromium:
    def __init__(self, state: _FakeState):
        self._state = state

    async def launch(self, *, headless: bool, args: list[str]) -> _FakeBrowser:
        del headless
        self._state.launch_calls += 1
        self._state.launch_args = list(args)
        return _FakeBrowser(self._state)


class _FakePlaywright:
    def __init__(self, state: _FakeState):
        self.chromium = _FakeChromium(state)
        self._state = state

    async def stop(self) -> None:
        self._state.playwright_stops += 1


class _FakePlaywrightStarter:
    def __init__(self, state: _FakeState):
        self._state = state

    async def start(self) -> _FakePlaywright:
        self._state.playwright_starts += 1
        return _FakePlaywright(self._state)


def _install_fake_playwright(monkeypatch: pytest.MonkeyPatch, state: _FakeState) -> None:
    playwright_module = types.ModuleType("playwright")
    playwright_module.__path__ = []

    async_api_module = types.ModuleType("playwright.async_api")

    class _FakeTimeoutError(Exception):
        pass

    def _async_playwright():
        return _FakePlaywrightStarter(state)

    async_api_module.TimeoutError = _FakeTimeoutError
    async_api_module.async_playwright = _async_playwright

    monkeypatch.setitem(sys.modules, "playwright", playwright_module)
    monkeypatch.setitem(sys.modules, "playwright.async_api", async_api_module)


def _settings(
    *,
    max_concurrency: int = 1,
    browser_args: tuple[str, ...] = ("--disable-dev-shm-usage",),
    capture_url_template: str = "https://m.bilibili.com/dynamic/{dyn_id}",
    long_screenshot_enabled: bool = False,
    opus_fallback_enabled: bool = True,
    opus_fallback_url_template: str = "https://www.bilibili.com/opus/{dyn_id}",
) -> Settings:
    return Settings(
        discord_token="x",
        notify_channel_id=1,
        guild_id=None,
        bili_voice_fixed_channel_id=None,
        poll_interval_seconds=30,
        dynamic_enabled=True,
        dynamic_poll_interval_seconds=60,
        dynamic_request_gap_seconds=0,
        dynamic_screenshot_enabled=True,
        dynamic_screenshot_template="https://example.com/{dyn_id}.jpg",
        dynamic_browser_screenshot_enabled=True,
        dynamic_browser_timeout_seconds=20,
        dynamic_browser_max_concurrency=max_concurrency,
        dynamic_browser_args=browser_args,
        dynamic_browser_capture_url_template=capture_url_template,
        dynamic_browser_long_screenshot_enabled=long_screenshot_enabled,
        dynamic_browser_opus_fallback_enabled=opus_fallback_enabled,
        dynamic_browser_opus_fallback_url_template=opus_fallback_url_template,
        dynamic_browser_ua="test-ua",
        dynamic_captcha_address="",
        dynamic_captcha_token="harukabot",
        sqlite_path=":memory:",
        log_level="INFO",
        bili_voice_enabled=True,
        bili_voice_streamlink_quality="audio_only",
        bili_voice_ffmpeg_path="",
    )


@pytest.mark.asyncio
async def test_capture_reuses_single_browser(monkeypatch: pytest.MonkeyPatch):
    state = _FakeState()
    _install_fake_playwright(monkeypatch, state)

    screenshotter = DynamicScreenshotter(_settings(browser_args=("--disable-dev-shm-usage", "--foo")))
    first = await screenshotter.capture(100)
    second = await screenshotter.capture(101)

    assert first.error is None
    assert first.image_bytes == b"card"
    assert second.error is None
    assert second.image_bytes == b"card"
    assert state.playwright_starts == 1
    assert state.launch_calls == 1
    assert state.new_context_calls == 2
    assert state.launch_args == ["--disable-dev-shm-usage", "--foo"]

    await screenshotter.aclose()

    assert state.browser_closes == 1
    assert state.playwright_stops == 1


@pytest.mark.asyncio
async def test_capture_respects_max_concurrency(monkeypatch: pytest.MonkeyPatch):
    state = _FakeState(gate_event=asyncio.Event())
    _install_fake_playwright(monkeypatch, state)

    screenshotter = DynamicScreenshotter(_settings(max_concurrency=1))

    first = asyncio.create_task(screenshotter.capture(200))
    await asyncio.wait_for(state.first_goto_entered.wait(), timeout=1)

    second = asyncio.create_task(screenshotter.capture(201))
    await asyncio.sleep(0.05)
    assert state.new_context_calls == 1
    assert state.max_active_contexts == 1

    state.gate_event.set()
    await asyncio.gather(first, second)

    assert state.new_context_calls == 2
    assert state.max_active_contexts == 1

    await screenshotter.aclose()


@pytest.mark.asyncio
async def test_capture_uses_custom_capture_url_template(monkeypatch: pytest.MonkeyPatch):
    state = _FakeState()
    _install_fake_playwright(monkeypatch, state)

    screenshotter = DynamicScreenshotter(
        _settings(
            capture_url_template="https://app.bilibili.com/dynamic/{dyn_id}?from={dynamic_url}",
        )
    )
    result = await screenshotter.capture(300, "https://t.bilibili.com/300")

    assert result.error is None
    assert state.last_goto_url == "https://app.bilibili.com/dynamic/300?from=https://t.bilibili.com/300"
    await screenshotter.aclose()


@pytest.mark.asyncio
async def test_capture_long_screenshot_mode_uses_full_page(monkeypatch: pytest.MonkeyPatch):
    state = _FakeState()
    _install_fake_playwright(monkeypatch, state)

    screenshotter = DynamicScreenshotter(_settings(long_screenshot_enabled=True))
    result = await screenshotter.capture(400)

    assert result.error is None
    assert result.image_bytes == b"full-page"
    assert state.full_page_screenshots == 1
    assert state.card_screenshots == 0
    await screenshotter.aclose()


@pytest.mark.asyncio
async def test_capture_falls_back_to_opus_on_app_gate(monkeypatch: pytest.MonkeyPatch):
    state = _FakeState()
    _install_fake_playwright(monkeypatch, state)

    screenshotter = DynamicScreenshotter(_settings())
    urls: list[str] = []

    async def _fake_capture_from_url(*, browser, dynamic_id, dynamic_url, url, timeout_ms):  # noqa: ARG001
        urls.append(url)
        if len(urls) == 1:
            return DynamicScreenshot(image_bytes=None, error="app-gated")
        return DynamicScreenshot(image_bytes=b"opus-fallback", error=None)

    monkeypatch.setattr(screenshotter, "_capture_from_url", _fake_capture_from_url)

    result = await screenshotter.capture(500, "https://t.bilibili.com/500")

    assert result.image_bytes == b"opus-fallback"
    assert result.error is None
    assert urls == [
        "https://m.bilibili.com/dynamic/500",
        "https://www.bilibili.com/opus/500",
    ]
    await screenshotter.aclose()


@pytest.mark.asyncio
async def test_capture_skips_opus_fallback_when_disabled(monkeypatch: pytest.MonkeyPatch):
    state = _FakeState()
    _install_fake_playwright(monkeypatch, state)

    screenshotter = DynamicScreenshotter(_settings(opus_fallback_enabled=False))
    urls: list[str] = []

    async def _fake_capture_from_url(*, browser, dynamic_id, dynamic_url, url, timeout_ms):  # noqa: ARG001
        urls.append(url)
        return DynamicScreenshot(image_bytes=None, error="app-gated")

    monkeypatch.setattr(screenshotter, "_capture_from_url", _fake_capture_from_url)

    result = await screenshotter.capture(501, "https://t.bilibili.com/501")

    assert result.image_bytes is None
    assert result.error == "app-gated"
    assert urls == ["https://m.bilibili.com/dynamic/501"]
    await screenshotter.aclose()
