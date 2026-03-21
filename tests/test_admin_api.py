import pytest
import os
from httpx import AsyncClient, ASGITransport
from tests.conftest import make_auth_header

@pytest.fixture
def app(db_pool):
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "999:test")
    os.environ.setdefault("MINI_APP_URL", "http://localhost:3000")
    from backend.api.app import create_app
    return create_app(pool=db_pool)

async def test_admin_stats_forbidden_for_non_admin(app):
    headers = make_auth_header(user_id=9999, bot_token="999:test")  # non-admin
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/admin/stats", headers=headers)
    assert resp.status_code == 403

async def test_settings_validation_rejects_bad_interval(app, db_pool):
    # Insert superadmin
    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO admins (chat_id, added_by) VALUES (1, 1) ON CONFLICT DO NOTHING")
    headers = make_auth_header(user_id=1, bot_token="999:test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/admin/settings",
            json={"poll_interval_seconds": 0.1},
            headers=headers,
        )
    assert resp.status_code == 422
