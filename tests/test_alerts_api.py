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

async def test_healthz(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

async def test_alerts_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/alerts")
    assert resp.status_code == 401  # no auth header → HTTPBearer(auto_error=False) returns 401

async def test_alerts_returns_list(app, db_pool):
    from backend.db import insert_alert_if_new
    await insert_alert_if_new(db_pool, "api-test-1", "title", ["תל אביב"])
    headers = make_auth_header(user_id=1, bot_token="999:test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/alerts", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
