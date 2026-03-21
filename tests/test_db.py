import pytest
import asyncpg

async def test_schema_creates_all_tables(db_pool):
    async with db_pool.acquire() as conn:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        table_names = {row["tablename"] for row in tables}
    assert "subscribers" in table_names
    assert "subscription_events" in table_names
    assert "subscriber_filters" in table_names
    assert "areas" in table_names
    assert "alerts_history" in table_names
    assert "admins" in table_names
    assert "bot_settings" in table_names

async def test_bot_settings_seeded(db_pool):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT value FROM bot_settings WHERE key = 'poll_interval_seconds'"
        )
    assert row is not None
    assert float(row["value"]) == 1.5

async def test_insert_subscriber(db_pool):
    from backend.db import upsert_subscriber, get_subscriber
    await upsert_subscriber(db_pool, chat_id=999, language="he")
    sub = await get_subscriber(db_pool, chat_id=999)
    assert sub["chat_id"] == 999
    assert sub["active"] is True
    assert sub["language"] == "he"
