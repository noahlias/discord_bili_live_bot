from __future__ import annotations

import sys

from dotenv import load_dotenv
from loguru import logger

from .bili_client import BiliClient
from .bot import BiliDiscordBot
from .config import Settings
from .db import SubscriptionStore
from .dota import DotaClient, DotaService
from .dynamic_client import DynamicClient
from .status_tracker import StatusTracker


def _setup_logger(level: str) -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )


def main() -> None:
    load_dotenv()
    settings = Settings.from_env()
    _setup_logger(settings.log_level)

    store = SubscriptionStore(settings.sqlite_path)
    client = BiliClient()
    dynamic_client = DynamicClient()
    dota_client = DotaClient(timeout_seconds=settings.dota_http_timeout_seconds)
    dota_service = DotaService(
        dota_client,
        recent_match_limit=settings.dota_recent_match_limit,
    )
    tracker = StatusTracker()

    bot = BiliDiscordBot(
        settings=settings,
        store=store,
        bili_client=client,
        dynamic_client=dynamic_client,
        tracker=tracker,
        dota_service=dota_service,
    )
    bot.run(settings.discord_token, log_handler=None)
