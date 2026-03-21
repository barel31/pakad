import pytest
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

TEST_DB_URL = os.environ["DATABASE_URL"]

@pytest.fixture(scope="session")
async def db_pool():
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=3)
    from backend.db import create_schema, seed_initial_data
    await create_schema(pool)
    await seed_initial_data(pool, poll_interval=1.5, superadmin_id=None)
    yield pool
    await pool.close()

# Shared helper used by test_alerts_api.py and test_admin_api.py
import time, hmac as _hmac, hashlib, json, urllib.parse

def make_auth_header(user_id: int, bot_token: str) -> dict:
    """Build a valid Telegram initData Authorization header for testing."""
    auth_date = str(int(time.time()))
    user_json = json.dumps({"id": user_id, "first_name": "T"})
    params = {"user": user_json, "auth_date": auth_date, "query_id": "x"}
    dcs = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    sk = _hmac.HMAC(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = _hmac.HMAC(sk, dcs.encode(), hashlib.sha256).hexdigest()
    params["hash"] = h
    return {"Authorization": f"tma {urllib.parse.urlencode(params)}"}
