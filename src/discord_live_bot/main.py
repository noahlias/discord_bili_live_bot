from __future__ import annotations

import sys

from dotenv import load_dotenv
from loguru import logger

from .bili_client import BiliClient
from .bot import BiliDiscordBot
from .config import Settings
from .db import SubscriptionStore
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
    tracker = StatusTracker()

    bot = BiliDiscordBot(settings=settings, store=store, bili_client=client, tracker=tracker)
    bot.run(settings.discord_token, log_handler=None)
