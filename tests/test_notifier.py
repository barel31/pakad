import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from backend.notifier import Notifier

def make_pool_mock(subscribers, filters_by_chat=None):
    pool = MagicMock()
    pool.acquire = MagicMock()
    return pool

async def test_fan_out_sends_to_all_active(db_pool):
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    notifier = Notifier(bot=bot, pool=db_pool)

    # Insert two test subscribers
    from backend.db import upsert_subscriber
    await upsert_subscriber(db_pool, chat_id=1001, language="he")
    await upsert_subscriber(db_pool, chat_id=1002, language="en")

    alert = {
        "id": "alert-fanout-test",
        "title": "ירי רקטות וטילים",
        "data": ["תל אביב"],
        "desc": "היכנסו",
    }
    await notifier.handle_alert(alert)
    assert bot.send_message.call_count == 2

async def test_forbidden_error_deactivates_subscriber(db_pool):
    from aiogram.exceptions import TelegramForbiddenError
    from backend.db import upsert_subscriber, get_subscriber

    await upsert_subscriber(db_pool, chat_id=2001, language="he")
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=TelegramForbiddenError(method=MagicMock(), message="blocked"))
    notifier = Notifier(bot=bot, pool=db_pool)

    alert = {"id": "alert-forbidden-test", "title": "t", "data": ["תל אביב"], "desc": "d"}
    await notifier.handle_alert(alert)

    sub = await get_subscriber(db_pool, chat_id=2001)
    assert sub["active"] is False

async def test_duplicate_alert_skipped(db_pool):
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    notifier = Notifier(bot=bot, pool=db_pool)

    alert = {"id": "alert-dup-test", "title": "t", "data": ["תל אביב"], "desc": "d"}
    await notifier.handle_alert(alert)
    first_count = bot.send_message.call_count
    bot.send_message.reset_mock()
    # Second call with same oref_id — should be skipped
    await notifier.handle_alert(alert)
    assert bot.send_message.call_count == 0
