from __future__ import annotations

import os
from dataclasses import dataclass


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _required_int(name: str) -> int:
    value = _require_env(name)
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _optional_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Environment variable {name} must be a boolean")


@dataclass(frozen=True)
class Settings:
    discord_token: str
    notify_channel_id: int
    guild_id: int | None
    poll_interval_seconds: int
    dynamic_enabled: bool
    dynamic_poll_interval_seconds: int
    dynamic_request_gap_seconds: float
    dynamic_screenshot_enabled: bool
    dynamic_screenshot_template: str
    dynamic_browser_screenshot_enabled: bool
    dynamic_browser_timeout_seconds: int
    dynamic_browser_max_concurrency: int
    dynamic_browser_args: tuple[str, ...]
    dynamic_browser_capture_url_template: str
    dynamic_browser_long_screenshot_enabled: bool
    dynamic_browser_opus_fallback_enabled: bool
    dynamic_browser_opus_fallback_url_template: str
    dynamic_browser_ua: str
    dynamic_captcha_address: str
    dynamic_captcha_token: str
    sqlite_path: str
    log_level: str
    dota_enabled: bool = True
    dota_recent_match_limit: int = 5
    dota_http_timeout_seconds: int = 15

    @classmethod
    def from_env(cls) -> "Settings":
        poll_interval_raw = os.getenv("POLL_INTERVAL_SECONDS", "30").strip() or "30"
        try:
            poll_interval = int(poll_interval_raw)
        except ValueError as exc:
            raise ValueError("POLL_INTERVAL_SECONDS must be an integer") from exc
        if poll_interval <= 0:
            raise ValueError("POLL_INTERVAL_SECONDS must be greater than 0")

        dynamic_enabled = _optional_bool("BILI_DYNAMIC_ENABLED", False)

        dynamic_poll_interval_raw = (
            os.getenv("BILI_DYNAMIC_POLL_INTERVAL_SECONDS", "60").strip() or "60"
        )
        try:
            dynamic_poll_interval = int(dynamic_poll_interval_raw)
        except ValueError as exc:
            raise ValueError("BILI_DYNAMIC_POLL_INTERVAL_SECONDS must be an integer") from exc
        if dynamic_poll_interval < 20:
            raise ValueError("BILI_DYNAMIC_POLL_INTERVAL_SECONDS must be at least 20")

        dynamic_request_gap_raw = os.getenv("BILI_DYNAMIC_REQUEST_GAP_SECONDS", "3").strip() or "3"
        try:
            dynamic_request_gap = float(dynamic_request_gap_raw)
        except ValueError as exc:
            raise ValueError("BILI_DYNAMIC_REQUEST_GAP_SECONDS must be a number") from exc
        if dynamic_request_gap < 0:
            raise ValueError("BILI_DYNAMIC_REQUEST_GAP_SECONDS must be >= 0")

        dynamic_screenshot_enabled = _optional_bool("BILI_DYNAMIC_SCREENSHOT_ENABLED", True)
        dynamic_screenshot_template = (
            os.getenv(
                "BILI_DYNAMIC_SCREENSHOT_TEMPLATE",
                "https://image.thum.io/get/width/1200/noanimate/https://t.bilibili.com/{dyn_id}",
            ).strip()
            or "https://image.thum.io/get/width/1200/noanimate/https://t.bilibili.com/{dyn_id}"
        )
        dynamic_browser_screenshot_enabled = _optional_bool(
            "BILI_DYNAMIC_BROWSER_SCREENSHOT_ENABLED",
            True,
        )
        dynamic_browser_timeout_raw = (
            os.getenv("BILI_DYNAMIC_BROWSER_TIMEOUT_SECONDS", "25").strip() or "25"
        )
        try:
            dynamic_browser_timeout_seconds = int(dynamic_browser_timeout_raw)
        except ValueError as exc:
            raise ValueError("BILI_DYNAMIC_BROWSER_TIMEOUT_SECONDS must be an integer") from exc
        if dynamic_browser_timeout_seconds <= 0:
            raise ValueError("BILI_DYNAMIC_BROWSER_TIMEOUT_SECONDS must be > 0")
        dynamic_browser_max_concurrency_raw = (
            os.getenv("BILI_DYNAMIC_BROWSER_MAX_CONCURRENCY", "1").strip() or "1"
        )
        try:
            dynamic_browser_max_concurrency = int(dynamic_browser_max_concurrency_raw)
        except ValueError as exc:
            raise ValueError("BILI_DYNAMIC_BROWSER_MAX_CONCURRENCY must be an integer") from exc
        if dynamic_browser_max_concurrency <= 0:
            raise ValueError("BILI_DYNAMIC_BROWSER_MAX_CONCURRENCY must be > 0")
        dynamic_browser_args_raw = (
            os.getenv("BILI_DYNAMIC_BROWSER_ARGS", "--disable-dev-shm-usage").strip()
            or "--disable-dev-shm-usage"
        )
        dynamic_browser_args = tuple(
            value.strip() for value in dynamic_browser_args_raw.split(",") if value.strip()
        )
        dynamic_browser_capture_url_template = (
            os.getenv(
                "BILI_DYNAMIC_BROWSER_CAPTURE_URL_TEMPLATE",
                "https://m.bilibili.com/dynamic/{dyn_id}",
            ).strip()
            or "https://m.bilibili.com/dynamic/{dyn_id}"
        )
        dynamic_browser_long_screenshot_enabled = _optional_bool(
            "BILI_DYNAMIC_BROWSER_LONG_SCREENSHOT_ENABLED",
            False,
        )
        dynamic_browser_opus_fallback_enabled = _optional_bool(
            "BILI_DYNAMIC_BROWSER_OPUS_FALLBACK_ENABLED",
            True,
        )
        dynamic_browser_opus_fallback_url_template = (
            os.getenv(
                "BILI_DYNAMIC_BROWSER_OPUS_FALLBACK_URL_TEMPLATE",
                "https://www.bilibili.com/opus/{dyn_id}",
            ).strip()
            or "https://www.bilibili.com/opus/{dyn_id}"
        )
        dynamic_browser_ua = (
            os.getenv(
                "BILI_DYNAMIC_BROWSER_UA",
                (
                    "Mozilla/5.0 (Linux; Android 10; RMX1911) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/100.0.4896.127 Mobile Safari/537.36"
                ),
            ).strip()
            or (
                "Mozilla/5.0 (Linux; Android 10; RMX1911) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/100.0.4896.127 Mobile Safari/537.36"
            )
        )
        dynamic_captcha_address = os.getenv("BILI_DYNAMIC_CAPTCHA_ADDRESS", "").strip()
        dynamic_captcha_token = os.getenv("BILI_DYNAMIC_CAPTCHA_TOKEN", "harukabot").strip() or "harukabot"

        dota_enabled = _optional_bool("DOTA_ENABLED", True)
        dota_recent_match_limit_raw = os.getenv("DOTA_RECENT_MATCH_LIMIT", "5").strip() or "5"
        try:
            dota_recent_match_limit = int(dota_recent_match_limit_raw)
        except ValueError as exc:
            raise ValueError("DOTA_RECENT_MATCH_LIMIT must be an integer") from exc
        if dota_recent_match_limit <= 0 or dota_recent_match_limit > 10:
            raise ValueError("DOTA_RECENT_MATCH_LIMIT must be between 1 and 10")

        dota_http_timeout_raw = os.getenv("DOTA_HTTP_TIMEOUT_SECONDS", "15").strip() or "15"
        try:
            dota_http_timeout_seconds = int(dota_http_timeout_raw)
        except ValueError as exc:
            raise ValueError("DOTA_HTTP_TIMEOUT_SECONDS must be an integer") from exc
        if dota_http_timeout_seconds <= 0:
            raise ValueError("DOTA_HTTP_TIMEOUT_SECONDS must be > 0")

        sqlite_path = os.getenv("SQLITE_PATH", "data/subscriptions.db").strip() or "data/subscriptions.db"
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

        return cls(
            discord_token=_require_env("DISCORD_TOKEN"),
            notify_channel_id=_required_int("DISCORD_NOTIFY_CHANNEL_ID"),
            guild_id=_optional_int("DISCORD_GUILD_ID"),
            poll_interval_seconds=poll_interval,
            dynamic_enabled=dynamic_enabled,
            dynamic_poll_interval_seconds=dynamic_poll_interval,
            dynamic_request_gap_seconds=dynamic_request_gap,
            dynamic_screenshot_enabled=dynamic_screenshot_enabled,
            dynamic_screenshot_template=dynamic_screenshot_template,
            dynamic_browser_screenshot_enabled=dynamic_browser_screenshot_enabled,
            dynamic_browser_timeout_seconds=dynamic_browser_timeout_seconds,
            dynamic_browser_max_concurrency=dynamic_browser_max_concurrency,
            dynamic_browser_args=dynamic_browser_args,
            dynamic_browser_capture_url_template=dynamic_browser_capture_url_template,
            dynamic_browser_long_screenshot_enabled=dynamic_browser_long_screenshot_enabled,
            dynamic_browser_opus_fallback_enabled=dynamic_browser_opus_fallback_enabled,
            dynamic_browser_opus_fallback_url_template=dynamic_browser_opus_fallback_url_template,
            dynamic_browser_ua=dynamic_browser_ua,
            dynamic_captcha_address=dynamic_captcha_address,
            dynamic_captcha_token=dynamic_captcha_token,
            dota_enabled=dota_enabled,
            dota_recent_match_limit=dota_recent_match_limit,
            dota_http_timeout_seconds=dota_http_timeout_seconds,
            sqlite_path=sqlite_path,
            log_level=log_level,
        )
