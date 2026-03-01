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


@dataclass(frozen=True)
class Settings:
    discord_token: str
    notify_channel_id: int
    guild_id: int | None
    poll_interval_seconds: int
    sqlite_path: str
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        poll_interval_raw = os.getenv("POLL_INTERVAL_SECONDS", "30").strip() or "30"
        try:
            poll_interval = int(poll_interval_raw)
        except ValueError as exc:
            raise ValueError("POLL_INTERVAL_SECONDS must be an integer") from exc
        if poll_interval <= 0:
            raise ValueError("POLL_INTERVAL_SECONDS must be greater than 0")

        sqlite_path = os.getenv("SQLITE_PATH", "data/subscriptions.db").strip() or "data/subscriptions.db"
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

        return cls(
            discord_token=_require_env("DISCORD_TOKEN"),
            notify_channel_id=_required_int("DISCORD_NOTIFY_CHANNEL_ID"),
            guild_id=_optional_int("DISCORD_GUILD_ID"),
            poll_interval_seconds=poll_interval,
            sqlite_path=sqlite_path,
            log_level=log_level,
        )
