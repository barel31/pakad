import logging
import functools
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import asyncpg
from backend.db import (
    upsert_subscriber, deactivate_subscriber, get_subscriber,
    get_subscriber_filters, add_filter, clear_filters, get_setting
)
from backend.areas import AREAS, normalize_area_input
from backend.messages import render

logger = logging.getLogger(__name__)


def _resolve_language(lang_code: str | None) -> str:
    if not lang_code:
        return "he"
    code = lang_code.lower()
    if code in ("iw", "he"):
        return "he"
    if code.startswith("en"):
        return "en"
    return "he"


def make_app_button(url: str, language: str) -> InlineKeyboardMarkup:
    label = "פתח אפליקציה 📊" if language == "he" else "Open App 📊"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url))
    ]])


async def cmd_start(message: Message, *, pool: asyncpg.Pool, mini_app_url: str) -> None:
    lang = _resolve_language(message.from_user.language_code)
    await upsert_subscriber(pool, chat_id=message.from_user.id, language=lang)
    await message.answer(
        render("start_welcome", lang),
        reply_markup=make_app_button(mini_app_url, lang),
    )


async def cmd_stop(message: Message, *, pool: asyncpg.Pool) -> None:
    sub = await get_subscriber(pool, message.from_user.id)
    lang = sub["language"] if sub else "he"
    await deactivate_subscriber(pool, chat_id=message.from_user.id)
    await message.answer(render("stop_confirmation", lang))


async def cmd_filter(message: Message, *, pool: asyncpg.Pool) -> None:
    sub = await get_subscriber(pool, message.from_user.id)
    lang = sub["language"] if sub else "he"
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(render("filter_not_found", lang, area=""))
        return
    area_input = parts[1].strip()
    matched = normalize_area_input(area_input)
    if not matched:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name FROM areas WHERE LOWER(name) = LOWER($1)", area_input
            )
            matched = row["name"] if row else None
    if not matched:
        await message.answer(render("filter_not_found", lang, area=area_input))
        return
    added = await add_filter(pool, chat_id=message.from_user.id, area=matched)
    if not added:
        await message.answer(render("filter_limit_reached", lang))
    else:
        await message.answer(render("filter_added", lang, area=matched))


async def cmd_filters(message: Message, *, pool: asyncpg.Pool) -> None:
    sub = await get_subscriber(pool, message.from_user.id)
    lang = sub["language"] if sub else "he"
    filters = await get_subscriber_filters(pool, message.from_user.id)
    if not filters:
        await message.answer(render("no_filters", lang))
    else:
        await message.answer("\n".join(f"• {f}" for f in filters))


async def cmd_clearfilters(message: Message, *, pool: asyncpg.Pool) -> None:
    sub = await get_subscriber(pool, message.from_user.id)
    lang = sub["language"] if sub else "he"
    await clear_filters(pool, chat_id=message.from_user.id)
    await message.answer(render("filters_cleared", lang))


async def cmd_areas(message: Message, *, pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT name FROM areas ORDER BY name")
    areas = [row["name"] for row in rows] or AREAS
    await message.answer("\n".join(f"• {a}" for a in areas))


async def cmd_status(message: Message, *, pool: asyncpg.Pool) -> None:
    sub = await get_subscriber(pool, message.from_user.id)
    if not sub:
        await message.answer("לא רשום / Not subscribed. Use /start")
        return
    lang = sub["language"]
    filters = await get_subscriber_filters(pool, message.from_user.id)
    filters_str = ", ".join(filters) if filters else ("הכל" if lang == "he" else "all")
    await message.answer(render("status_active", lang, language=lang, filters=filters_str))


async def cmd_language(message: Message, *, pool: asyncpg.Pool) -> None:
    sub = await get_subscriber(pool, message.from_user.id)
    current_lang = sub["language"] if sub else "he"
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or parts[1].strip() not in ("he", "en"):
        await message.answer(render("language_invalid", current_lang))
        return
    new_lang = parts[1].strip()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE subscribers SET language = $1 WHERE chat_id = $2",
            new_lang, message.from_user.id
        )
    await message.answer(render("language_set", new_lang))


async def cmd_app(message: Message, *, pool: asyncpg.Pool, mini_app_url: str) -> None:
    sub = await get_subscriber(pool, message.from_user.id)
    lang = sub["language"] if sub else "he"
    await message.answer(
        "📊",
        reply_markup=make_app_button(mini_app_url, lang),
    )


async def cmd_help(message: Message, *, pool: asyncpg.Pool) -> None:
    sub = await get_subscriber(pool, message.from_user.id)
    lang = sub["language"] if sub else "he"
    await message.answer(render("help", lang))


def make_dispatcher(pool: asyncpg.Pool, mini_app_url: str) -> Dispatcher:
    router = Router()
    p = functools.partial

    router.message.register(p(cmd_start, pool=pool, mini_app_url=mini_app_url), Command("start"))
    router.message.register(p(cmd_stop, pool=pool), Command("stop"))
    router.message.register(p(cmd_filter, pool=pool), Command("filter"))
    router.message.register(p(cmd_filters, pool=pool), Command("filters"))
    router.message.register(p(cmd_clearfilters, pool=pool), Command("clearfilters"))
    router.message.register(p(cmd_areas, pool=pool), Command("areas"))
    router.message.register(p(cmd_status, pool=pool), Command("status"))
    router.message.register(p(cmd_language, pool=pool), Command("language"))
    router.message.register(p(cmd_app, pool=pool, mini_app_url=mini_app_url), Command("app"))
    router.message.register(p(cmd_help, pool=pool), Command("help"))

    dp = Dispatcher()
    dp.include_router(router)
    return dp
