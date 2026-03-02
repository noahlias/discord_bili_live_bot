from __future__ import annotations

import contextlib
from dataclasses import dataclass

from loguru import logger

from .config import Settings


@dataclass(frozen=True)
class DynamicScreenshot:
    image_bytes: bytes | None
    error: str | None


class DynamicScreenshotter:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def capture(self, dynamic_id: int) -> DynamicScreenshot:
        if not self._settings.dynamic_screenshot_enabled:
            return DynamicScreenshot(image_bytes=None, error="disabled")
        if not self._settings.dynamic_browser_screenshot_enabled:
            return DynamicScreenshot(image_bytes=None, error="browser-disabled")

        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except Exception:
            return DynamicScreenshot(image_bytes=None, error="playwright-not-installed")

        url = f"https://m.bilibili.com/dynamic/{dynamic_id}"
        timeout_ms = self._settings.dynamic_browser_timeout_seconds * 1000

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(
                        user_agent=self._settings.dynamic_browser_ua,
                        viewport={"width": 1080, "height": 1920},
                        device_scale_factor=2,
                    )

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
                    await browser.close()
        except PlaywrightTimeoutError:
            return DynamicScreenshot(image_bytes=None, error="timeout")
        except Exception as exc:
            logger.debug("Dynamic screenshot failed for {}: {}", dynamic_id, exc)
            return DynamicScreenshot(image_bytes=None, error="capture-failed")

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
