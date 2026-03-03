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

    async def capture(self, dynamic_id: int, dynamic_url: str = "") -> DynamicScreenshot:
        if not self._settings.dynamic_screenshot_enabled:
            return DynamicScreenshot(image_bytes=None, error="disabled")
        if not self._settings.dynamic_browser_screenshot_enabled:
            return DynamicScreenshot(image_bytes=None, error="browser-disabled")

        try:
            timeout_error = await self._ensure_browser_started()
        except RuntimeError:
            return DynamicScreenshot(image_bytes=None, error="playwright-not-installed")

        primary_url = self._capture_url(dynamic_id, dynamic_url)
        timeout_ms = self._settings.dynamic_browser_timeout_seconds * 1000

        try:
            async with self._capture_semaphore:
                browser = await self._get_browser()
                primary = await self._capture_from_url(
                    browser=browser,
                    dynamic_id=dynamic_id,
                    dynamic_url=dynamic_url,
                    url=primary_url,
                    timeout_ms=timeout_ms,
                )
                if not self._should_try_opus_fallback(primary, primary_url):
                    return primary

                fallback_url = self._opus_fallback_url(dynamic_id, dynamic_url)
                logger.debug(
                    "Primary dynamic screenshot blocked for {}. Fallback to opus url: {}",
                    dynamic_id,
                    fallback_url,
                )
                fallback = await self._capture_from_url(
                    browser=browser,
                    dynamic_id=dynamic_id,
                    dynamic_url=dynamic_url,
                    url=fallback_url,
                    timeout_ms=timeout_ms,
                )
                if fallback.image_bytes:
                    return fallback
                return fallback if not primary.image_bytes else primary
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

    async def _capture_from_url(
        self,
        *,
        browser: Any,
        dynamic_id: int,
        dynamic_url: str,
        url: str,
        timeout_ms: int,
    ) -> DynamicScreenshot:
        del dynamic_id, dynamic_url
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

            if self._settings.dynamic_browser_long_screenshot_enabled:
                is_opus = self._is_opus_url(url)
                if not is_opus:
                    await self._expand_long_text(page)
                if not is_opus and await self._is_app_gate_visible(page):
                    return DynamicScreenshot(image_bytes=None, error="app-gated")
                image = await page.screenshot(full_page=True, type="jpeg", quality=95)
                return DynamicScreenshot(image_bytes=image, error=None)

            if not self._is_opus_url(url) and await self._is_app_gate_visible(page):
                return DynamicScreenshot(image_bytes=None, error="app-gated")

            card = None
            for selector in [".opus-modules", ".dyn-card", ".dyn-content", ".m-opus-layout", ".opus-detail"]:
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

    def _capture_url(self, dynamic_id: int, dynamic_url: str) -> str:
        template = self._settings.dynamic_browser_capture_url_template
        fallback_url = f"https://t.bilibili.com/{dynamic_id}"
        try:
            return template.format(
                dyn_id=dynamic_id,
                dynamic_url=dynamic_url or fallback_url,
            )
        except Exception:
            logger.warning("Invalid BILI_DYNAMIC_BROWSER_CAPTURE_URL_TEMPLATE, fallback to default mobile URL")
            return f"https://m.bilibili.com/dynamic/{dynamic_id}"

    def _opus_fallback_url(self, dynamic_id: int, dynamic_url: str) -> str:
        template = self._settings.dynamic_browser_opus_fallback_url_template
        fallback_url = f"https://www.bilibili.com/opus/{dynamic_id}"
        try:
            return template.format(
                dyn_id=dynamic_id,
                dynamic_url=dynamic_url or f"https://t.bilibili.com/{dynamic_id}",
            )
        except Exception:
            logger.warning(
                "Invalid BILI_DYNAMIC_BROWSER_OPUS_FALLBACK_URL_TEMPLATE, fallback to default opus URL"
            )
            return fallback_url

    def _should_try_opus_fallback(self, result: DynamicScreenshot, primary_url: str) -> bool:
        if not self._settings.dynamic_browser_opus_fallback_enabled:
            return False
        if self._is_opus_url(primary_url):
            return False
        return result.image_bytes is None and result.error == "app-gated"

    def _is_opus_url(self, url: str) -> bool:
        return "/opus/" in url

    async def _expand_long_text(self, page: Any) -> None:
        with contextlib.suppress(Exception):
            expanded = await page.evaluate(
                """
                () => {
                  const targets = ['展开阅读全文', '展开全文', '全文'];
                  const nodes = Array.from(document.querySelectorAll('*'));
                  for (const node of nodes) {
                    const text = (node.textContent || '').trim();
                    if (!targets.includes(text)) {
                      continue;
                    }
                    node.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    return true;
                  }
                  return false;
                }
                """
            )
            if expanded:
                await page.wait_for_timeout(400)

    async def _is_app_gate_visible(self, page: Any) -> bool:
        with contextlib.suppress(Exception):
            return bool(
                await page.evaluate(
                    """
                    () => {
                      const text = (document.body && document.body.innerText) || '';
                      return (
                        text.includes('打开APP即可浏览完整内容') ||
                        text.includes('浏览方式（推荐使用）') ||
                        text.includes('你感兴趣的视频都在B站')
                      );
                    }
                    """
                )
            )
        return False

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
