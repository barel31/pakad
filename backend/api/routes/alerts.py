from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from datetime import datetime, timezone, timedelta
from backend.api.auth import get_current_user

router = APIRouter()

@router.get("/alerts")
async def get_alerts(
    request: Request,
    page: int = Query(1, ge=1),
    area: str | None = None,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    _user_id: int = Depends(get_current_user),
):
    pool = request.app.state.pool
    limit = 50
    offset = (page - 1) * limit
    async with pool.acquire() as conn:
        query = "SELECT id, oref_id, title, areas, received_at FROM alerts_history"
        conditions, params = [], []
        if area:
            conditions.append(f"${len(params)+1} = ANY(areas)")
            params.append(area)
        if from_:
            conditions.append(f"received_at >= ${len(params)+1}")
            params.append(from_)
        if to:
            conditions.append(f"received_at <= ${len(params)+1}")
            params.append(to)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        params.append(limit)
        params.append(offset)
        query += f" ORDER BY received_at DESC LIMIT ${len(params)-1} OFFSET ${len(params)}"
        rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]

@router.get("/alerts/live")
async def get_live_alert(
    request: Request,
    _user_id: int = Depends(get_current_user),
):
    pool = request.app.state.pool
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM alerts_history WHERE received_at >= $1 ORDER BY received_at DESC LIMIT 1",
            cutoff,
        )
    return dict(row) if row else None
