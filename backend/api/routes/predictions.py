from fastapi import APIRouter, Request, Depends
from backend.api.auth import get_current_user

router = APIRouter()
MIN_RECORDS = 10

@router.get("/predictions")
async def get_predictions(
    request: Request,
    _user_id: int = Depends(get_current_user),
):
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM alerts_history")
        if total < MIN_RECORDS:
            return {"insufficient_data": True, "record_count": total, "minimum": MIN_RECORDS}
        peak_hour = await conn.fetchrow("""
            SELECT EXTRACT(HOUR FROM received_at) AS hour, COUNT(*) AS count
            FROM alerts_history GROUP BY hour ORDER BY count DESC LIMIT 1
        """)
        peak_day = await conn.fetchrow("""
            SELECT TO_CHAR(received_at, 'Day') AS day_name, COUNT(*) AS count
            FROM alerts_history GROUP BY day_name ORDER BY count DESC LIMIT 1
        """)
        most_targeted = await conn.fetchrow("""
            SELECT unnest(areas) AS area, COUNT(*) AS count
            FROM alerts_history GROUP BY area ORDER BY count DESC LIMIT 1
        """)
    return {
        "insufficient_data": False,
        "peak_hour": dict(peak_hour) if peak_hour else None,
        "peak_day": dict(peak_day) if peak_day else None,
        "most_targeted_area": dict(most_targeted) if most_targeted else None,
    }
