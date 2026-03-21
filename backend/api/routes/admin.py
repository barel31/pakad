from fastapi import APIRouter, Request, Depends, HTTPException, Body
from pydantic import BaseModel, field_validator
from backend.api.auth import require_admin
from backend.db import set_setting, get_setting

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

class SettingsUpdate(BaseModel):
    poll_interval_seconds: float | None = None
    bot_enabled: bool | None = None

    @field_validator("poll_interval_seconds")
    @classmethod
    def validate_interval(cls, v):
        if v is not None and not (1.0 <= v <= 10.0):
            raise ValueError("poll_interval_seconds must be between 1.0 and 10.0")
        return v

@router.get("/stats")
async def admin_stats(request: Request):
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM subscribers")
        active = await conn.fetchval("SELECT COUNT(*) FROM subscribers WHERE active = TRUE AND blocked = FALSE")
        blocked = await conn.fetchval("SELECT COUNT(*) FROM subscribers WHERE blocked = TRUE")
        inactive = await conn.fetchval(
            "SELECT COUNT(*) FROM subscribers WHERE active = FALSE AND blocked = FALSE"
        )
        alerts_today = await conn.fetchval(
            "SELECT COUNT(*) FROM alerts_history WHERE received_at >= NOW() - INTERVAL '1 day'"
        )
        last_alert = await conn.fetchrow(
            "SELECT received_at FROM alerts_history ORDER BY received_at DESC LIMIT 1"
        )
    bot_enabled = await get_setting(pool, "bot_enabled")
    poll_interval = await get_setting(pool, "poll_interval_seconds")
    return {
        "subscribers": {"total": total, "active": active, "blocked": blocked, "inactive": inactive},
        "alerts_today": alerts_today,
        "last_alert_at": last_alert["received_at"].isoformat() if last_alert else None,
        "bot_enabled": bot_enabled == "true",
        "poll_interval_seconds": float(poll_interval) if poll_interval else 1.5,
    }

@router.get("/subscribers")
async def list_subscribers(request: Request, page: int = 1):
    pool = request.app.state.pool
    limit, offset = 50, (page - 1) * 50
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT chat_id, active, blocked, language, subscribed_at FROM subscribers "
            "ORDER BY subscribed_at DESC LIMIT $1 OFFSET $2", limit, offset
        )
    return [dict(r) for r in rows]

@router.post("/subscribers/{chat_id}/block")
async def block_subscriber(chat_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await conn.execute("UPDATE subscribers SET blocked = TRUE WHERE chat_id = $1", chat_id)
    return {"ok": True}

@router.post("/subscribers/{chat_id}/unblock")
async def unblock_subscriber(chat_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await conn.execute("UPDATE subscribers SET blocked = FALSE WHERE chat_id = $1", chat_id)
    return {"ok": True}

class BroadcastBody(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def validate_length(cls, v):
        if len(v) > 4096:
            raise ValueError("Message exceeds Telegram's 4096 character limit")
        return v

@router.post("/broadcast")
async def broadcast(request: Request, body: BroadcastBody):
    import asyncio
    from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
    pool = request.app.state.pool
    bot = request.app.state.bot
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT chat_id FROM subscribers WHERE active = TRUE AND blocked = FALSE"
        )
    for row in rows:
        try:
            await bot.send_message(chat_id=row["chat_id"], text=body.message)
        except TelegramForbiddenError:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE subscribers SET active = FALSE WHERE chat_id = $1", row["chat_id"]
                )
        except TelegramRetryAfter as e:
            await asyncio.sleep(min(e.retry_after, 30))
            try:
                await bot.send_message(chat_id=row["chat_id"], text=body.message)
            except TelegramForbiddenError:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE subscribers SET active = FALSE WHERE chat_id = $1", row["chat_id"]
                    )
            except Exception:
                pass
        except Exception:
            pass
    return {"ok": True, "recipients": len(rows)}

@router.get("/settings")
async def get_settings(request: Request):
    pool = request.app.state.pool
    return {
        "poll_interval_seconds": float(await get_setting(pool, "poll_interval_seconds") or "1.5"),
        "bot_enabled": (await get_setting(pool, "bot_enabled")) == "true",
    }

@router.put("/settings")
async def update_settings(request: Request, body: SettingsUpdate):
    pool = request.app.state.pool
    if body.poll_interval_seconds is not None:
        await set_setting(pool, "poll_interval_seconds", str(body.poll_interval_seconds))
    if body.bot_enabled is not None:
        await set_setting(pool, "bot_enabled", "true" if body.bot_enabled else "false")
    return {"ok": True}

@router.get("/areas")
async def list_areas(request: Request):
    async with request.app.state.pool.acquire() as conn:
        rows = await conn.fetch("SELECT name FROM areas ORDER BY name")
    return [row["name"] for row in rows]

@router.post("/areas")
async def add_area(request: Request, name: str = Body(..., embed=True)):
    async with request.app.state.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO areas (name) VALUES ($1) ON CONFLICT DO NOTHING", name
        )
    return {"ok": True}

@router.delete("/areas/{name}")
async def delete_area(name: str, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await conn.execute("DELETE FROM areas WHERE name = $1", name)
    return {"ok": True}

@router.get("/admins")
async def list_admins(request: Request):
    async with request.app.state.pool.acquire() as conn:
        rows = await conn.fetch("SELECT chat_id, added_by, added_at FROM admins")
    return [dict(r) for r in rows]

@router.post("/admins")
async def add_admin(request: Request, chat_id: int = Body(..., embed=True), admin_id: int = Depends(require_admin)):
    async with request.app.state.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO admins (chat_id, added_by) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            chat_id, admin_id
        )
    return {"ok": True}

@router.delete("/admins/{chat_id}")
async def remove_admin(chat_id: int, request: Request, admin_id: int = Depends(require_admin)):
    async with request.app.state.pool.acquire() as conn:
        async with conn.transaction():
            count = await conn.fetchval("SELECT COUNT(*) FROM admins")
            if count <= 1:
                raise HTTPException(status_code=400, detail="Cannot remove last admin")
            if chat_id == admin_id:
                raise HTTPException(status_code=400, detail="Cannot remove yourself")
            await conn.execute("DELETE FROM admins WHERE chat_id = $1", chat_id)
    return {"ok": True}
