from fastapi import APIRouter, Request, Depends
from backend.api.auth import get_current_user

router = APIRouter()

@router.get("/analytics/global")
async def global_analytics(
    request: Request,
    _user_id: int = Depends(get_current_user),
):
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        hourly = await conn.fetch("""
            SELECT EXTRACT(HOUR FROM received_at) AS hour, COUNT(*) AS count
            FROM alerts_history GROUP BY hour ORDER BY hour
        """)
        daily = await conn.fetch("""
            SELECT EXTRACT(DOW FROM received_at) AS dow, COUNT(*) AS count
            FROM alerts_history GROUP BY dow ORDER BY dow
        """)
        top_areas = await conn.fetch("""
            SELECT unnest(areas) AS area, COUNT(*) AS count
            FROM alerts_history GROUP BY area ORDER BY count DESC LIMIT 20
        """)
        trend = await conn.fetch("""
            SELECT DATE(received_at) AS day, COUNT(*) AS count
            FROM alerts_history
            WHERE received_at >= NOW() - INTERVAL '7 days'
            GROUP BY day ORDER BY day
        """)
    return {
        "hourly_heatmap": [dict(r) for r in hourly],
        "day_of_week": [dict(r) for r in daily],
        "top_areas": [dict(r) for r in top_areas],
        "seven_day_trend": [dict(r) for r in trend],
    }

@router.get("/analytics/personal")
async def personal_analytics(
    request: Request,
    user_id: int = Depends(get_current_user),
):
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        sub = await conn.fetchrow(
            "SELECT * FROM subscribers WHERE chat_id = $1", user_id
        )
        if not sub:
            return {"error": "not_subscribed"}
        filters = await conn.fetch(
            "SELECT area FROM subscriber_filters WHERE chat_id = $1", user_id
        )
        events = await conn.fetch("""
            SELECT event, occurred_at FROM subscription_events
            WHERE chat_id = $1 ORDER BY occurred_at
        """, user_id)
        total_alerts = await conn.fetchval("SELECT COUNT(*) FROM alerts_history")
        filter_list = [r["area"] for r in filters]
        if filter_list:
            matched = await conn.fetchval("""
                SELECT COUNT(*) FROM alerts_history
                WHERE areas && $1::text[]
            """, filter_list)
        else:
            matched = total_alerts
    return {
        "total_alerts": total_alerts,
        "matched_alerts": matched,
        "filters": filter_list,
        "subscription_history": [dict(r) for r in events],
    }
