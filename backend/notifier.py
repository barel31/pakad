import asyncio
import logging
from datetime import datetime, timezone
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
import asyncpg
from backend.db import (
    insert_alert_if_new, get_active_subscribers,
    get_subscriber_filters, deactivate_subscriber, get_setting
)
from backend.messages import render_alert

logger = logging.getLogger(__name__)
MAX_RETRY_AFTER = 30  # seconds cap

class Notifier:
    def __init__(self, bot: Bot, pool: asyncpg.Pool):
        self._bot = bot
        self._pool = pool

    async def run(self, queue: asyncio.Queue) -> None:
        while True:
            alert = await queue.get()
            enabled = await get_setting(self._pool, "bot_enabled")
            if enabled != "true":
                logger.info("Bot disabled — skipping fan-out")
                continue
            await self.handle_alert(alert)

    async def handle_alert(self, alert: dict) -> None:
        oref_id = str(alert["id"])
        title = alert.get("title", "")
        areas = alert.get("data", [])
        time_str = datetime.now(timezone.utc).strftime("%H:%M:%S")

        is_new = await insert_alert_if_new(self._pool, oref_id, title, areas)
        if not is_new:
            logger.info("Duplicate alert %s — skipping fan-out", oref_id)
            return

        subscribers = await get_active_subscribers(self._pool)
        for sub in subscribers:
            chat_id = sub["chat_id"]
            language = sub["language"]
            filters = await get_subscriber_filters(self._pool, chat_id)
            if filters and not any(a in filters for a in areas):
                continue
            await self._send(chat_id, language, title, areas, time_str)

    async def _send(
        self, chat_id: int, language: str,
        title: str, areas: list[str], time_str: str
    ) -> None:
        msg = render_alert(language=language, title=title, areas=areas, time_str=time_str)
        while True:
            try:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=msg,
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            except TelegramForbiddenError:
                logger.info("User %s blocked bot — deactivating", chat_id)
                await deactivate_subscriber(self._pool, chat_id)
                return
            except TelegramRetryAfter as e:
                wait = min(e.retry_after, MAX_RETRY_AFTER)
                await asyncio.sleep(wait)
                # loop continues, retries the send
            except Exception as e:
                logger.error("Failed to send to %s: %s", chat_id, e)
                return
