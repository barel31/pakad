import asyncpg
import os
from typing import Optional

async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=5)

async def create_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id BIGINT PRIMARY KEY,
                subscribed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                blocked BOOLEAN NOT NULL DEFAULT FALSE,
                language TEXT NOT NULL DEFAULT 'he'
            );

            CREATE TABLE IF NOT EXISTS subscription_events (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL REFERENCES subscribers(chat_id),
                event TEXT NOT NULL CHECK (event IN ('subscribed', 'unsubscribed')),
                occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS areas (
                name TEXT PRIMARY KEY,
                added_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS subscriber_filters (
                chat_id BIGINT NOT NULL REFERENCES subscribers(chat_id) ON DELETE CASCADE,
                area TEXT NOT NULL REFERENCES areas(name) ON DELETE CASCADE,
                PRIMARY KEY (chat_id, area)
            );

            CREATE TABLE IF NOT EXISTS alerts_history (
                id SERIAL PRIMARY KEY,
                oref_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                areas TEXT[] NOT NULL,
                received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS admins (
                chat_id BIGINT PRIMARY KEY,
                added_by BIGINT,
                added_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

async def seed_initial_data(
    pool: asyncpg.Pool,
    poll_interval: float,
    superadmin_id: Optional[int],
) -> None:
    from backend.areas import AREAS
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bot_settings (key, value)
            VALUES ('poll_interval_seconds', $1), ('bot_enabled', 'true')
            ON CONFLICT (key) DO NOTHING
        """, str(poll_interval))
        if superadmin_id:
            await conn.execute("""
                INSERT INTO admins (chat_id, added_by)
                VALUES ($1, $1)
                ON CONFLICT (chat_id) DO NOTHING
            """, superadmin_id)
        for area in AREAS:
            await conn.execute("""
                INSERT INTO areas (name) VALUES ($1)
                ON CONFLICT (name) DO NOTHING
            """, area)

async def upsert_subscriber(
    pool: asyncpg.Pool, chat_id: int, language: str = "he"
) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO subscribers (chat_id, language, subscribed_at, active)
            VALUES ($1, $2, NOW(), TRUE)
            ON CONFLICT (chat_id) DO UPDATE
            SET active = TRUE, subscribed_at = NOW(), language = EXCLUDED.language
        """, chat_id, language)
        await conn.execute("""
            INSERT INTO subscription_events (chat_id, event)
            VALUES ($1, 'subscribed')
        """, chat_id)

async def deactivate_subscriber(pool: asyncpg.Pool, chat_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE subscribers SET active = FALSE WHERE chat_id = $1", chat_id
        )
        await conn.execute("""
            INSERT INTO subscription_events (chat_id, event)
            VALUES ($1, 'unsubscribed')
        """, chat_id)

async def get_subscriber(pool: asyncpg.Pool, chat_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM subscribers WHERE chat_id = $1", chat_id
        )

async def get_active_subscribers(pool: asyncpg.Pool) -> list:
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT chat_id, language FROM subscribers WHERE active = TRUE AND blocked = FALSE"
        )

async def get_subscriber_filters(pool: asyncpg.Pool, chat_id: int) -> list[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT area FROM subscriber_filters WHERE chat_id = $1", chat_id
        )
        return [row["area"] for row in rows]

async def add_filter(pool: asyncpg.Pool, chat_id: int, area: str) -> bool:
    """Returns False if limit (10) reached, True if inserted. Atomic via transaction."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM subscriber_filters WHERE chat_id = $1 FOR UPDATE",
                chat_id,
            )
            if count >= 10:
                return False
            await conn.execute("""
                INSERT INTO subscriber_filters (chat_id, area)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
            """, chat_id, area)
            return True

async def clear_filters(pool: asyncpg.Pool, chat_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM subscriber_filters WHERE chat_id = $1", chat_id
        )

async def is_admin(pool: asyncpg.Pool, chat_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM admins WHERE chat_id = $1", chat_id
        )
        return row is not None

async def get_setting(pool: asyncpg.Pool, key: str) -> str:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT value FROM bot_settings WHERE key = $1", key
        )
        return row["value"] if row else None

async def set_setting(pool: asyncpg.Pool, key: str, value: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bot_settings (key, value)
            VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, key, value)

async def insert_alert_if_new(
    pool: asyncpg.Pool,
    oref_id: str,
    title: str,
    areas: list[str],
) -> bool:
    """Returns True if inserted (new alert), False if already existed (duplicate)."""
    async with pool.acquire() as conn:
        result = await conn.execute("""
            INSERT INTO alerts_history (oref_id, title, areas, received_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (oref_id) DO NOTHING
        """, oref_id, title, areas)
        return result == "INSERT 0 1"
