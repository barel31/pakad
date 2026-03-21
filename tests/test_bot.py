import pytest
from unittest.mock import AsyncMock, MagicMock, patch

async def test_start_command_subscribes_user(db_pool):
    from backend.bot import cmd_start
    from backend.db import get_subscriber

    message = AsyncMock()
    message.from_user.id = 3001
    message.from_user.language_code = "he"
    message.answer = AsyncMock()

    await cmd_start(message, pool=db_pool, mini_app_url="https://app.example.com")

    sub = await get_subscriber(db_pool, chat_id=3001)
    assert sub is not None
    assert sub["active"] is True
    message.answer.assert_called_once()

async def test_filter_command_adds_filter(db_pool):
    from backend.bot import cmd_filter
    from backend.db import upsert_subscriber, get_subscriber_filters

    await upsert_subscriber(db_pool, chat_id=3002, language="he")
    message = AsyncMock()
    message.from_user.id = 3002
    message.text = "/filter תל אביב - מרכז העיר"
    message.answer = AsyncMock()

    await cmd_filter(message, pool=db_pool)
    filters = await get_subscriber_filters(db_pool, chat_id=3002)
    assert "תל אביב - מרכז העיר" in filters
    message.answer.assert_called_once()

async def test_filter_invalid_area_returns_error(db_pool):
    from backend.bot import cmd_filter
    from backend.db import upsert_subscriber

    await upsert_subscriber(db_pool, chat_id=3003, language="en")
    message = AsyncMock()
    message.from_user.id = 3003
    message.text = "/filter nonexistent area xyz"
    message.answer = AsyncMock()

    await cmd_filter(message, pool=db_pool)
    call_args = message.answer.call_args[0][0]
    assert "not found" in call_args or "לא נמצא" in call_args
