from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import Any

from loguru import logger

from .config import Settings


@dataclass(frozen=True)
class DynamicScreenshot:
    image_bytes: bytes | None
    error: str | None


class DynamicScreenshotter:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._init_lock = asyncio.Lock()
        self._capture_semaphore = asyncio.Semaphore(settings.dynamic_browser_max_concurrency)
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._playwright_timeout_error: type[Exception] | None = None

    async def capture(self, dynamic_id: int) -> DynamicScreenshot:
        if not self._settings.dynamic_screenshot_enabled:
            return DynamicScreenshot(image_bytes=None, error="disabled")
        if not self._settings.dynamic_browser_screenshot_enabled:
            return DynamicScreenshot(image_bytes=None, error="browser-disabled")

        try:
            timeout_error = await self._ensure_browser_started()
        except RuntimeError:
            return DynamicScreenshot(image_bytes=None, error="playwright-not-installed")

        url = f"https://m.bilibili.com/dynamic/{dynamic_id}"
        timeout_ms = self._settings.dynamic_browser_timeout_seconds * 1000

        try:
            async with self._capture_semaphore:
                browser = await self._get_browser()
                context = await browser.new_context(
                    user_agent=self._settings.dynamic_browser_ua,
                    viewport={"width": 1080, "height": 1920},
                    device_scale_factor=2,
                )
                try:
                    page = await context.new_page()

                    page = await self._goto_with_optional_captcha(page, url, timeout_ms)
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(300)

                    if "404" in page.url:
                        return DynamicScreenshot(image_bytes=None, error="not-found")

                    with contextlib.suppress(Exception):
                        await page.evaluate(
                            """
                            document.querySelectorAll(
                              '.openapp, .open-app, .m-navbar, .m-dynamic-float-openapp, .login-panel'
                            ).forEach(el => el.remove());
                            """
                        )

                    card = None
                    for selector in [".opus-modules", ".dyn-card", ".dyn-content", ".m-opus-layout"]:
                        with contextlib.suppress(Exception):
                            await page.wait_for_selector(selector, timeout=2000)
                            card = await page.query_selector(selector)
                            if card:
                                break

                    if card is not None:
                        image = await card.screenshot(type="jpeg", quality=100)
                        return DynamicScreenshot(image_bytes=image, error=None)

                    image = await page.screenshot(full_page=True, type="jpeg", quality=95)
                    return DynamicScreenshot(image_bytes=image, error="full-page-fallback")
                finally:
                    with contextlib.suppress(Exception):
                        await context.close()
        except timeout_error:
            return DynamicScreenshot(image_bytes=None, error="timeout")
        except Exception as exc:
            logger.debug("Dynamic screenshot failed for {}: {}", dynamic_id, exc)
            return DynamicScreenshot(image_bytes=None, error="capture-failed")

    async def aclose(self) -> None:
        async with self._init_lock:
            browser = self._browser
            playwright = self._playwright
            self._browser = None
            self._playwright = None
            self._playwright_timeout_error = None

        if browser is not None:
            with contextlib.suppress(Exception):
                await browser.close()
        if playwright is not None:
            with contextlib.suppress(Exception):
                await playwright.stop()

    async def _ensure_browser_started(self) -> type[Exception]:
        if self._browser is not None and self._playwright_timeout_error is not None:
            with contextlib.suppress(Exception):
                if self._browser.is_connected():
                    return self._playwright_timeout_error

        async with self._init_lock:
            if self._browser is not None and self._playwright_timeout_error is not None:
                with contextlib.suppress(Exception):
                    if self._browser.is_connected():
                        return self._playwright_timeout_error

            await self._close_started_browser_locked()

            try:
                from playwright.async_api import TimeoutError as PlaywrightTimeoutError
                from playwright.async_api import async_playwright
            except Exception as exc:
                raise RuntimeError("playwright-not-installed") from exc

            playwright = await async_playwright().start()
            try:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=list(self._settings.dynamic_browser_args),
                )
            except Exception:
                with contextlib.suppress(Exception):
                    await playwright.stop()
                raise

            self._playwright = playwright
            self._browser = browser
            self._playwright_timeout_error = PlaywrightTimeoutError
            return PlaywrightTimeoutError

    async def _get_browser(self) -> Any:
        browser = self._browser
        if browser is not None:
            with contextlib.suppress(Exception):
                if browser.is_connected():
                    return browser
        await self._ensure_browser_started()
        browser = self._browser
        if browser is None:
            raise RuntimeError("browser-not-initialized")
        return browser

    async def _close_started_browser_locked(self) -> None:
        browser = self._browser
        playwright = self._playwright
        self._browser = None
        self._playwright = None
        self._playwright_timeout_error = None

        if browser is not None:
            with contextlib.suppress(Exception):
                await browser.close()
        if playwright is not None:
            with contextlib.suppress(Exception):
                await playwright.stop()

    async def _goto_with_optional_captcha(self, page, url: str, timeout_ms: int):
        if not self._settings.dynamic_captcha_address:
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            return page

        try:
            from aunly_captcha_solver import CaptchaInfer
        except Exception:
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            return page

        captcha = CaptchaInfer(
            self._settings.dynamic_captcha_address,
            self._settings.dynamic_captcha_token,
        )
        return await captcha.solve_captcha(page, url)
