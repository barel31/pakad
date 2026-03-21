# Pikud HaOref Telegram Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telegram bot that delivers real-time Pikud HaOref rocket alerts with an embedded Mini App for alert history, predictions, personal analytics, and admin panel — fully bilingual (Hebrew/English).

**Architecture:** Single Python process on Railway Hobby (aiogram bot + FastAPI server sharing one asyncio event loop), backed by PostgreSQL. React + Vite Mini App deployed to Vercel, authenticated via Telegram `initData` HMAC.

**Tech Stack:** Python 3.11, aiogram 3.x, FastAPI, uvicorn, asyncpg, aiohttp, pytest, pytest-asyncio, React 18, Vite, TypeScript, react-i18next, recharts, axios, @twa-dev/sdk

**Spec:** `docs/superpowers/specs/2026-03-21-pikud-haoref-telegram-bot-design.md`

---

## File Map

```
pakad/
├── backend/
│   ├── main.py                    — asyncio entry point; wires all tasks
│   ├── oref_poller.py             — polls Oref API, deduplicates, puts to Queue
│   ├── notifier.py                — consumes Queue, writes DB, fans out Telegram msgs
│   ├── bot.py                     — aiogram Dispatcher + all command handlers
│   ├── db.py                      — asyncpg pool, schema DDL, query helpers
│   ├── areas.py                   — hardcoded canonical Hebrew area list
│   ├── messages.py                — bilingual bot message templates
│   ├── api/
│   │   ├── app.py                 — FastAPI instance, CORS, healthz, uvicorn Server
│   │   ├── auth.py                — initData HMAC + auth_date validation
│   │   └── routes/
│   │       ├── alerts.py          — GET /api/alerts, GET /api/alerts/live
│   │       ├── analytics.py       — GET /api/analytics/global, /personal
│   │       ├── predictions.py     — GET /api/predictions
│   │       └── admin.py           — all /api/admin/* endpoints
│   └── requirements.txt
├── tests/
│   ├── conftest.py                — pytest fixtures (DB, bot, http client)
│   ├── test_db.py                 — schema creation, basic CRUD
│   ├── test_oref_poller.py        — polling logic + dedup
│   ├── test_notifier.py           — fan-out, error handling
│   ├── test_bot.py                — command handlers
│   ├── test_auth.py               — initData validation
│   ├── test_alerts_api.py         — alerts endpoints
│   ├── test_analytics_api.py      — analytics endpoints
│   ├── test_predictions_api.py    — predictions endpoint
│   └── test_admin_api.py          — admin endpoints
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                — router + layout
│   │   ├── i18n.ts                — react-i18next setup
│   │   ├── api/
│   │   │   └── client.ts          — axios instance with initData auth header
│   │   ├── pages/
│   │   │   ├── History.tsx
│   │   │   ├── Predictions.tsx
│   │   │   ├── Personal.tsx
│   │   │   └── Admin.tsx
│   │   ├── components/
│   │   │   ├── AlertCard.tsx
│   │   │   ├── LiveBanner.tsx
│   │   │   ├── LanguageToggle.tsx
│   │   │   └── EmptyState.tsx
│   │   └── locales/
│   │       ├── he.json
│   │       └── en.json
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── railway.toml
└── .env.example
```

---

## Phase 1: Foundation

### Task 1: Project scaffold

**Files:**
- Create: `.env.example`
- Create: `railway.toml`
- Create: `backend/requirements.txt`
- Create: `pyproject.toml`

- [ ] **Step 1: Create root files**

`.env.example`:
```
TELEGRAM_BOT_TOKEN=
DATABASE_URL=postgresql://user:pass@host:5432/dbname
MINI_APP_URL=https://your-app.vercel.app
SUPERADMIN_CHAT_ID=123456789
POLL_INTERVAL_SECONDS=1.5
CORS_ORIGINS=https://your-app.vercel.app
API_PORT=8000
```

`railway.toml`:
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python backend/main.py"
restartPolicyType = "always"
healthcheckPath = "/healthz"
healthcheckTimeout = 10
```

- [ ] **Step 2: Create `backend/requirements.txt`**

```
aiogram==3.15.0
fastapi==0.115.0
uvicorn==0.30.0
asyncpg==0.29.0
aiohttp==3.10.0
python-dotenv==1.0.0
```

- [ ] **Step 3: Create `pyproject.toml` for tests**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = ["integration: marks tests as integration (require real DB)"]
```

- [ ] **Step 4: Create `tests/` directory with empty `__init__.py`**

```bash
mkdir -p tests backend/api/routes
touch tests/__init__.py backend/__init__.py backend/api/__init__.py backend/api/routes/__init__.py
```

- [ ] **Step 5: Install deps and verify**

```bash
cd backend && pip install -r requirements.txt
python -c "import aiogram, fastapi, asyncpg, aiohttp; print('OK')"
```
Expected output: `OK`

- [ ] **Step 6: Install test deps**

```bash
pip install pytest pytest-asyncio httpx pytest-mock
```

- [ ] **Step 7: Commit**

```bash
git init
git add .
git commit -m "chore: project scaffold — requirements, railway config, test setup"
```

---

### Task 2: Database layer

**Files:**
- Create: `backend/db.py`
- Create: `tests/conftest.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:
```python
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
```

- [ ] **Step 2: Create `tests/conftest.py`**

```python
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
    sk = _hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = _hmac.new(sk, dcs.encode(), hashlib.sha256).hexdigest()
    params["hash"] = h
    return {"Authorization": f"tma {urllib.parse.urlencode(params)}"}

# Note: make_auth_header uses the same algorithm as validate_init_data.
# It tests the round-trip but won't catch systematic errors in the algorithm itself.
# If auth is ever suspected broken, test against a known-good token from Telegram docs.
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_db.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` (db.py doesn't exist yet)

- [ ] **Step 4: Create `backend/db.py`**

```python
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
```

- [ ] **Step 5: Create `backend/areas.py`** (partial list — fill with complete Oref area list)

```python
# Full list sourced from https://www.oref.org.il
AREAS: list[str] = [
    "תל אביב - מרכז העיר",
    "תל אביב - דרום העיר",
    "תל אביב - צפון העיר",
    "רמת גן - כפר אז\"ר",
    "רמת גן - מרכז העיר",
    "גבעתיים",
    "חולון",
    "בת ים",
    "ירושלים",
    "חיפה",
    "באר שבע",
    "אשדוד",
    "אשקלון",
    "נתניה",
    "פתח תקווה",
    "ראשון לציון",
    "רחובות",
    "הרצליה",
    "כפר סבא",
    "מודיעין",
    "לוד",
    "רמלה",
    "עכו",
    "נהריה",
    "עפולה",
    "טבריה",
    "צפת",
    "קריית שמונה",
    "שדרות",
    "ספיר",
    # NOTE: Add the complete list from https://www.oref.org.il/Shelters/Pages/SafeRoomsEn.aspx
]

def normalize_area_input(text: str) -> str | None:
    """Return matching area name from AREAS or None if not found (case-insensitive strip)."""
    text = text.strip()
    for area in AREAS:
        if area.strip().lower() == text.lower():
            return area
    return None
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_db.py -v
```
Expected: 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/db.py backend/areas.py tests/conftest.py tests/test_db.py pyproject.toml
git commit -m "feat: database schema, pool, and query helpers"
```

---

### Task 3: Message templates

**Files:**
- Create: `backend/messages.py`
- Create: `tests/test_messages.py`

- [ ] **Step 1: Write failing test**

`tests/test_messages.py`:
```python
from backend.messages import render_alert, render

def test_render_alert_hebrew():
    msg = render_alert(
        language="he",
        title="ירי רקטות וטילים",
        areas=["תל אביב", "רמת גן"],
        time_str="14:32:07",
    )
    assert "ירי רקטות וטילים" in msg
    assert "תל אביב" in msg
    assert "14:32:07" in msg

def test_render_alert_english():
    msg = render_alert(
        language="en",
        title="ירי רקטות וטילים",
        areas=["תל אביב", "רמת גן"],
        time_str="14:32:07",
    )
    assert "Rocket" in msg
    assert "תל אביב" in msg   # areas always Hebrew
    assert "14:32:07" in msg

def test_render_command_response():
    msg = render("start_welcome", "he")
    assert isinstance(msg, str)
    assert len(msg) > 0

def test_render_unknown_key_raises():
    with pytest.raises(KeyError):
        render("nonexistent_key", "he")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_messages.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create `backend/messages.py`**

```python
from datetime import datetime

TEMPLATES: dict[str, dict[str, str]] = {
    "start_welcome": {
        "he": "ברוך הבא! 🚨\nנרשמת לקבלת התראות פיקוד העורף.\nהשתמש ב-/help לרשימת פקודות.",
        "en": "Welcome! 🚨\nYou are now subscribed to Pikud HaOref alerts.\nUse /help for commands.",
    },
    "stop_confirmation": {
        "he": "בוטל המנוי. לא תקבל יותר התראות.\nלהרשמה מחדש: /start",
        "en": "Unsubscribed. You will no longer receive alerts.\nTo resubscribe: /start",
    },
    "filter_added": {
        "he": "סינון נוסף: {area}",
        "en": "Filter added: {area}",
    },
    "filter_not_found": {
        "he": "האזור '{area}' לא נמצא. השתמש ב-/areas לרשימה מלאה.",
        "en": "Area '{area}' not found. Use /areas for the full list.",
    },
    "filter_limit_reached": {
        "he": "הגעת למגבלת 10 סינונים. השתמש ב-/clearfilters כדי לנקות.",
        "en": "You have reached the 10-filter limit. Use /clearfilters to reset.",
    },
    "filters_cleared": {
        "he": "כל הסינונים הוסרו. תקבל עכשיו את כל ההתראות.",
        "en": "All filters cleared. You will now receive all alerts.",
    },
    "no_filters": {
        "he": "אין לך סינונים פעילים — מקבל את כל ההתראות.",
        "en": "No active filters — you receive all alerts.",
    },
    "status_active": {
        "he": "מנוי פעיל ✅\nשפה: {language}\nסינונים: {filters}",
        "en": "Subscription active ✅\nLanguage: {language}\nFilters: {filters}",
    },
    "language_set": {
        "he": "שפה שונתה לעברית.",
        "en": "Language set to English.",
    },
    "language_invalid": {
        "he": "שפה לא חוקית. השתמש ב-/language he או /language en",
        "en": "Invalid language. Use /language he or /language en",
    },
    "help": {
        "he": (
            "/start — הרשמה להתראות\n"
            "/stop — ביטול מנוי\n"
            "/filter <אזור> — הוסף סינון אזור\n"
            "/filters — רשימת הסינונים שלך\n"
            "/clearfilters — נקה סינונים\n"
            "/areas — רשימת אזורים תקינים\n"
            "/status — סטטוס מנוי\n"
            "/language he|en — שנה שפה\n"
            "/app — פתח את האפליקציה"
        ),
        "en": (
            "/start — Subscribe to alerts\n"
            "/stop — Unsubscribe\n"
            "/filter <area> — Add area filter\n"
            "/filters — Your current filters\n"
            "/clearfilters — Clear all filters\n"
            "/areas — List valid areas\n"
            "/status — Subscription status\n"
            "/language he|en — Change language\n"
            "/app — Open the Mini App"
        ),
    },
}

def render(key: str, language: str, **kwargs) -> str:
    template = TEMPLATES[key][language]  # raises KeyError if missing
    return template.format(**kwargs) if kwargs else template

def render_alert(
    language: str,
    title: str,
    areas: list[str],
    time_str: str,
) -> str:
    areas_str = ", ".join(areas)
    if language == "he":
        return (
            f"🚨 *{title}*\n\n"
            f"📍 *אזורים:* {areas_str}\n"
            f"🕐 *שעה:* {time_str}\n\n"
            f"היכנסו למרחב המוגן מיד!"
        )
    return (
        f"🚨 *Rocket & Missile Fire*\n\n"
        f"📍 *Areas:* {areas_str}\n"
        f"🕐 *Time:* {time_str}\n\n"
        f"Enter a protected space immediately!"
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_messages.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/messages.py tests/test_messages.py
git commit -m "feat: bilingual bot message templates"
```

---

## Phase 2: Bot Core

### Task 4: Oref Poller

**Files:**
- Create: `backend/oref_poller.py`
- Create: `tests/test_oref_poller.py`

- [ ] **Step 1: Write failing tests**

`tests/test_oref_poller.py`:
```python
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from backend.oref_poller import OrefPoller

SAMPLE_ALERT = {
    "id": "12345",
    "cat": "1",
    "title": "ירי רקטות וטילים",
    "data": ["תל אביב", "רמת גן"],
    "desc": "היכנסו למרחב המוגן מיד",
}

def make_mock_session(response_data, status=200):
    """Build a mock aiohttp.ClientSession with a pre-configured GET response."""
    mock_response = AsyncMock()
    mock_response.status = status
    if isinstance(response_data, Exception):
        mock_response.json = AsyncMock(side_effect=response_data)
    else:
        mock_response.json = AsyncMock(return_value=response_data)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_response),
        __aexit__=AsyncMock(return_value=False),
    ))
    return mock_session

async def test_new_alert_puts_to_queue():
    queue = asyncio.Queue(maxsize=1)
    poller = OrefPoller(queue=queue, interval=0.1)
    session = make_mock_session(SAMPLE_ALERT)

    await poller._poll_once(session)
    # First call seeds last_alert_id without dispatching
    assert queue.empty()
    await poller._poll_once(session)
    # Same ID — no change
    assert queue.empty()

    session2 = make_mock_session({**SAMPLE_ALERT, "id": "99999"})
    await poller._poll_once(session2)
    assert not queue.empty()
    alert = queue.get_nowait()
    assert alert["id"] == "99999"

async def test_empty_response_is_ignored():
    queue = asyncio.Queue(maxsize=1)
    poller = OrefPoller(queue=queue, interval=0.1)
    session = make_mock_session(Exception("not JSON"))

    await poller._poll_once(session)  # should not raise
    assert queue.empty()

async def test_non_200_is_skipped():
    queue = asyncio.Queue(maxsize=1)
    poller = OrefPoller(queue=queue, interval=0.1)
    session = make_mock_session({}, status=503)

    await poller._poll_once(session)
    assert queue.empty()

async def test_full_queue_replaces_item():
    queue = asyncio.Queue(maxsize=1)
    await queue.put({"id": "old"})
    poller = OrefPoller(queue=queue, interval=0.1)
    poller._last_alert_id = "prev"  # seed so first different ID dispatches

    session = make_mock_session({**SAMPLE_ALERT, "id": "new"})
    await poller._poll_once(session)
    item = queue.get_nowait()
    assert item["id"] == "new"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_oref_poller.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create `backend/oref_poller.py`**

```python
import asyncio
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)

OREF_URL = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
OREF_HEADERS = {
    "Referer": "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
}

class OrefPoller:
    def __init__(self, queue: asyncio.Queue, interval: float = 1.5):
        self._queue = queue
        self._interval = interval
        self._last_alert_id: Optional[str] = None

    async def run(self) -> None:
        """Production entry point — uses a single persistent aiohttp session."""
        async with aiohttp.ClientSession() as session:
            while True:
                await self._poll_once(session)
                await asyncio.sleep(self._interval)

    async def _poll_once(self, session: aiohttp.ClientSession) -> None:
        """Poll the Oref API once. Accepts the session so tests can inject a mock."""
        try:
            async with session.get(
                OREF_URL, headers=OREF_HEADERS, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    logger.warning("Oref API returned %s", resp.status)
                    return
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    return  # empty or non-JSON = no active alert
                if not data or not isinstance(data, dict) or not data.get("id"):
                    return
                alert_id = str(data["id"])
                if self._last_alert_id is None:
                    # Seed on first call — don't dispatch
                    self._last_alert_id = alert_id
                    return
                if alert_id == self._last_alert_id:
                    return
                self._last_alert_id = alert_id
                self._dispatch(data)
        except asyncio.TimeoutError:
            logger.warning("Oref API timeout")
        except Exception as e:
            logger.warning("Oref poll error: %s", e)

    def _dispatch(self, alert: dict) -> None:
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self._queue.put_nowait(alert)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_oref_poller.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/oref_poller.py tests/test_oref_poller.py
git commit -m "feat: Oref API poller with deduplication and queue dispatch"
```

---

### Task 5: Notifier

**Files:**
- Create: `backend/notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write failing tests**

`tests/test_notifier.py`:
```python
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from backend.notifier import Notifier

def make_pool_mock(subscribers, filters_by_chat=None):
    pool = MagicMock()
    pool.acquire = MagicMock()
    return pool

async def test_fan_out_sends_to_all_active(db_pool):
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    notifier = Notifier(bot=bot, pool=db_pool)

    # Insert two test subscribers
    from backend.db import upsert_subscriber
    await upsert_subscriber(db_pool, chat_id=1001, language="he")
    await upsert_subscriber(db_pool, chat_id=1002, language="en")

    alert = {
        "id": "alert-fanout-test",
        "title": "ירי רקטות וטילים",
        "data": ["תל אביב"],
        "desc": "היכנסו",
    }
    await notifier.handle_alert(alert)
    assert bot.send_message.call_count == 2

async def test_forbidden_error_deactivates_subscriber(db_pool):
    from aiogram.exceptions import TelegramForbiddenError
    from backend.db import upsert_subscriber, get_subscriber

    await upsert_subscriber(db_pool, chat_id=2001, language="he")
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=TelegramForbiddenError(method=MagicMock(), message="blocked"))
    notifier = Notifier(bot=bot, pool=db_pool)

    alert = {"id": "alert-forbidden-test", "title": "t", "data": ["תל אביב"], "desc": "d"}
    await notifier.handle_alert(alert)

    sub = await get_subscriber(db_pool, chat_id=2001)
    assert sub["active"] is False

async def test_duplicate_alert_skipped(db_pool):
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    notifier = Notifier(bot=bot, pool=db_pool)

    alert = {"id": "alert-dup-test", "title": "t", "data": ["תל אביב"], "desc": "d"}
    await notifier.handle_alert(alert)
    first_count = bot.send_message.call_count
    bot.send_message.reset_mock()
    # Second call with same oref_id — should be skipped
    await notifier.handle_alert(alert)
    assert bot.send_message.call_count == 0
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_notifier.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create `backend/notifier.py`**

```python
import asyncio
import logging
from datetime import datetime, timezone
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfterError
import asyncpg
from backend.db import (
    insert_alert_if_new, get_active_subscribers,
    get_subscriber_filters, deactivate_subscriber, get_setting
)
from backend.messages import render_alert

logger = logging.getLogger(__name__)
MAX_RETRY_AFTER = 30  # seconds cap

class Notifier:
    def __init__(self, bot: Bot, pool: asyncpg.Pool):
        self._bot = bot
        self._pool = pool

    async def run(self, queue: asyncio.Queue) -> None:
        while True:
            alert = await queue.get()
            enabled = await get_setting(self._pool, "bot_enabled")
            if enabled != "true":
                logger.info("Bot disabled — skipping fan-out")
                continue
            await self.handle_alert(alert)

    async def handle_alert(self, alert: dict) -> None:
        oref_id = str(alert["id"])
        title = alert.get("title", "")
        areas = alert.get("data", [])
        time_str = datetime.now(timezone.utc).strftime("%H:%M:%S")

        is_new = await insert_alert_if_new(self._pool, oref_id, title, areas)
        if not is_new:
            logger.info("Duplicate alert %s — skipping fan-out", oref_id)
            return

        subscribers = await get_active_subscribers(self._pool)
        for sub in subscribers:
            chat_id = sub["chat_id"]
            language = sub["language"]
            filters = await get_subscriber_filters(self._pool, chat_id)
            if filters and not any(a in filters for a in areas):
                continue
            await self._send(chat_id, language, title, areas, time_str)

    async def _send(
        self, chat_id: int, language: str,
        title: str, areas: list[str], time_str: str
    ) -> None:
        msg = render_alert(language=language, title=title, areas=areas, time_str=time_str)
        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramForbiddenError:
            logger.info("User %s blocked bot — deactivating", chat_id)
            await deactivate_subscriber(self._pool, chat_id)
        except TelegramRetryAfterError as e:
            wait = min(e.retry_after, MAX_RETRY_AFTER)
            await asyncio.sleep(wait)
            await self._send(chat_id, language, title, areas, time_str)
        except Exception as e:
            logger.error("Failed to send to %s: %s", chat_id, e)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_notifier.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/notifier.py tests/test_notifier.py
git commit -m "feat: notifier with fan-out, dedup guard, and error handling"
```

---

### Task 6: Bot commands

**Files:**
- Create: `backend/bot.py`
- Create: `tests/test_bot.py`

- [ ] **Step 1: Write failing tests**

`tests/test_bot.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

async def test_start_command_subscribes_user(db_pool):
    from backend.bot import make_dispatcher
    from backend.db import get_subscriber

    bot = AsyncMock()
    dp = make_dispatcher(pool=db_pool, mini_app_url="https://app.example.com")

    message = AsyncMock()
    message.from_user.id = 3001
    message.from_user.language_code = "he"
    message.answer = AsyncMock()

    await dp.feed_update(bot, MagicMock(message=message, callback_query=None))
    # Direct handler test
    from backend.bot import cmd_start
    await cmd_start(message, pool=db_pool, mini_app_url="https://app.example.com")

    sub = await get_subscriber(db_pool, chat_id=3001)
    assert sub is not None
    assert sub["active"] is True
    message.answer.assert_called_once()

async def test_filter_command_adds_filter(db_pool):
    from backend.bot import cmd_filter
    from backend.db import upsert_subscriber, get_subscriber_filters

    await upsert_subscriber(db_pool, chat_id=3002, language="he")
    message = AsyncMock()
    message.from_user.id = 3002
    message.text = "/filter תל אביב - מרכז העיר"
    message.answer = AsyncMock()

    await cmd_filter(message, pool=db_pool)
    filters = await get_subscriber_filters(db_pool, chat_id=3002)
    assert "תל אביב - מרכז העיר" in filters
    message.answer.assert_called_once()

async def test_filter_invalid_area_returns_error(db_pool):
    from backend.bot import cmd_filter
    from backend.db import upsert_subscriber

    await upsert_subscriber(db_pool, chat_id=3003, language="en")
    message = AsyncMock()
    message.from_user.id = 3003
    message.text = "/filter nonexistent area xyz"
    message.answer = AsyncMock()

    await cmd_filter(message, pool=db_pool)
    call_args = message.answer.call_args[0][0]
    assert "not found" in call_args or "לא נמצא" in call_args
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_bot.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create `backend/bot.py`**

```python
import logging
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import asyncpg
from backend.db import (
    upsert_subscriber, deactivate_subscriber, get_subscriber,
    get_subscriber_filters, add_filter, clear_filters, set_setting, get_setting
)
from backend.areas import AREAS, normalize_area_input
from backend.messages import render, render_alert

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

def make_dispatcher(pool: asyncpg.Pool, mini_app_url: str) -> Dispatcher:
    router = Router()

    @router.message(Command("start"))
    async def cmd_start(message: Message):
        lang = _resolve_language(message.from_user.language_code)
        await upsert_subscriber(pool, chat_id=message.from_user.id, language=lang)
        await message.answer(
            render("start_welcome", lang),
            reply_markup=make_app_button(mini_app_url, lang),
        )

    @router.message(Command("stop"))
    async def cmd_stop(message: Message):
        sub = await get_subscriber(pool, message.from_user.id)
        lang = sub["language"] if sub else "he"
        await deactivate_subscriber(pool, chat_id=message.from_user.id)
        await message.answer(render("stop_confirmation", lang))

    @router.message(Command("filter"))
    async def cmd_filter(message: Message):
        sub = await get_subscriber(pool, message.from_user.id)
        lang = sub["language"] if sub else "he"
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer(render("filter_not_found", lang, area=""))
            return
        area_input = parts[1].strip()
        matched = normalize_area_input(area_input)
        if not matched:
            # Also check DB areas table
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

    @router.message(Command("filters"))
    async def cmd_filters(message: Message):
        sub = await get_subscriber(pool, message.from_user.id)
        lang = sub["language"] if sub else "he"
        filters = await get_subscriber_filters(pool, message.from_user.id)
        if not filters:
            await message.answer(render("no_filters", lang))
        else:
            await message.answer("\n".join(f"• {f}" for f in filters))

    @router.message(Command("clearfilters"))
    async def cmd_clearfilters(message: Message):
        sub = await get_subscriber(pool, message.from_user.id)
        lang = sub["language"] if sub else "he"
        await clear_filters(pool, chat_id=message.from_user.id)
        await message.answer(render("filters_cleared", lang))

    @router.message(Command("areas"))
    async def cmd_areas(message: Message):
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT name FROM areas ORDER BY name")
        areas = [row["name"] for row in rows] or AREAS
        await message.answer("\n".join(f"• {a}" for a in areas))

    @router.message(Command("status"))
    async def cmd_status(message: Message):
        sub = await get_subscriber(pool, message.from_user.id)
        if not sub:
            await message.answer("לא רשום / Not subscribed. Use /start")
            return
        lang = sub["language"]
        filters = await get_subscriber_filters(pool, message.from_user.id)
        filters_str = ", ".join(filters) if filters else ("הכל" if lang == "he" else "all")
        await message.answer(render("status_active", lang, language=lang, filters=filters_str))

    @router.message(Command("language"))
    async def cmd_language(message: Message):
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

    @router.message(Command("app"))
    async def cmd_app(message: Message):
        sub = await get_subscriber(pool, message.from_user.id)
        lang = sub["language"] if sub else "he"
        await message.answer(
            "📊" if lang == "he" else "📊",
            reply_markup=make_app_button(mini_app_url, lang),
        )

    @router.message(Command("help"))
    async def cmd_help(message: Message):
        sub = await get_subscriber(pool, message.from_user.id)
        lang = sub["language"] if sub else "he"
        await message.answer(render("help", lang))

    dp = Dispatcher()
    dp.include_router(router)
    return dp
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_bot.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/bot.py tests/test_bot.py
git commit -m "feat: aiogram bot command handlers"
```

---

### Task 7: Main entry point

**Files:**
- Create: `backend/main.py`

- [ ] **Step 1: Create `backend/main.py`**

```python
import asyncio
import logging
import os
from dotenv import load_dotenv
import uvicorn
from aiogram import Bot

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

async def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    db_url = os.environ["DATABASE_URL"]
    mini_app_url = os.environ["MINI_APP_URL"]
    superadmin_id_str = os.environ.get("SUPERADMIN_CHAT_ID")
    superadmin_id = int(superadmin_id_str) if superadmin_id_str else None
    poll_interval = float(os.environ.get("POLL_INTERVAL_SECONDS", "1.5"))
    port = int(os.environ.get("PORT", os.environ.get("API_PORT", "8000")))

    if not (1.0 <= poll_interval <= 10.0):
        raise ValueError(f"POLL_INTERVAL_SECONDS must be between 1.0 and 10.0, got {poll_interval}")

    from backend.db import create_pool, create_schema, seed_initial_data
    pool = await create_pool(db_url)
    await create_schema(pool)
    await seed_initial_data(pool, poll_interval=poll_interval, superadmin_id=superadmin_id)
    logger.info("Database ready")

    bot = Bot(token=token)

    from backend.api.app import create_app
    app = create_app(pool=pool)
    app.state.bot = bot  # required by /api/admin/broadcast
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)

    from backend.bot import make_dispatcher
    dp = make_dispatcher(pool=pool, mini_app_url=mini_app_url)

    queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    from backend.oref_poller import OrefPoller
    from backend.notifier import Notifier
    poller = OrefPoller(queue=queue, interval=poll_interval)
    notifier = Notifier(bot=bot, pool=pool)

    async def run_bot():
        await dp.start_polling(bot)

    async def run_notifier():
        await notifier.run(queue)

    logger.info("Starting all tasks on port %s", port)
    await asyncio.gather(
        server.serve(),
        poller.run(),
        run_notifier(),
        run_bot(),
    )

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Verify import chain**

```bash
cd backend && python -c "import main; print('imports OK')"
```
Expected: `imports OK`

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: asyncio entry point wiring bot, poller, notifier, and API"
```

---

## Phase 3: REST API

### Task 8: FastAPI app + auth

**Files:**
- Create: `backend/api/app.py`
- Create: `backend/api/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write failing auth tests**

`tests/test_auth.py`:
```python
import pytest
import time
import hmac
import hashlib
import urllib.parse
from backend.api.auth import validate_init_data, AuthError

BOT_TOKEN = "123456:ABC-test-token"

def make_init_data(user_id: int, bot_token: str, age_seconds: int = 0) -> str:
    auth_date = int(time.time()) - age_seconds
    data_dict = {
        "user": f'{{"id":{user_id},"first_name":"Test"}}',
        "auth_date": str(auth_date),
        "query_id": "test",
    }
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data_dict.items())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    data_dict["hash"] = hash_value
    return urllib.parse.urlencode(data_dict)

def test_valid_init_data_returns_user_id():
    init_data = make_init_data(user_id=42, bot_token=BOT_TOKEN)
    user_id = validate_init_data(init_data, bot_token=BOT_TOKEN)
    assert user_id == 42

def test_expired_init_data_raises():
    init_data = make_init_data(user_id=42, bot_token=BOT_TOKEN, age_seconds=7200)
    with pytest.raises(AuthError, match="expired"):
        validate_init_data(init_data, bot_token=BOT_TOKEN)

def test_invalid_hash_raises():
    init_data = make_init_data(user_id=42, bot_token=BOT_TOKEN)
    tampered = init_data + "&extra=evil"
    with pytest.raises(AuthError, match="invalid"):
        validate_init_data(tampered, bot_token=BOT_TOKEN)
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_auth.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create `backend/api/auth.py`**

```python
import hmac
import hashlib
import json
import time
import urllib.parse
from typing import Optional

class AuthError(Exception):
    pass

def validate_init_data(init_data: str, bot_token: str, max_age: int = 3600) -> int:
    """
    Validate Telegram Mini App initData string.
    Returns the user's Telegram ID on success.
    Raises AuthError on failure.
    """
    params = dict(urllib.parse.parse_qsl(init_data))
    received_hash = params.pop("hash", None)
    if not received_hash:
        raise AuthError("invalid: missing hash")

    auth_date = int(params.get("auth_date", 0))
    if time.time() - auth_date > max_age:
        raise AuthError(f"expired: auth_date is {int(time.time() - auth_date)}s old")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise AuthError("invalid: hash mismatch")

    user_data = json.loads(params.get("user", "{}"))
    user_id = user_data.get("id")
    if not user_id:
        raise AuthError("invalid: missing user.id")
    return int(user_id)
```

- [ ] **Step 4: Run auth tests**

```bash
pytest tests/test_auth.py -v
```
Expected: All PASS

- [ ] **Step 5: Create `backend/api/app.py`**

```python
import os
import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.api.routes import alerts, analytics, predictions, admin

def create_app(pool: asyncpg.Pool) -> FastAPI:
    app = FastAPI(title="Pikud HaOref API", docs_url=None, redoc_url=None)

    cors_origins = os.environ.get("CORS_ORIGINS", os.environ.get("MINI_APP_URL", "*"))
    origins = [o.strip() for o in cors_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.state.pool = pool
    app.state.bot_token = os.environ["TELEGRAM_BOT_TOKEN"]

    @app.get("/healthz")
    async def healthz():
        return JSONResponse({"status": "ok"})

    app.include_router(alerts.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(predictions.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")

    return app
```

- [ ] **Step 6: Add auth dependency helper to `backend/api/auth.py`**

Append to the file:
```python
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int:
    # Note: HTTPBearer returns 403 when no Authorization header is present (FastAPI default).
    # It returns 401 (from the raise below) when the header exists but fails validation.
    if not credentials or credentials.scheme.lower() != "tma":
        raise HTTPException(status_code=401, detail="Missing or invalid auth scheme")
    try:
        return validate_init_data(
            credentials.credentials,
            bot_token=request.app.state.bot_token,
        )
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

async def require_admin(
    request: Request,
    user_id: int = Depends(get_current_user),
) -> int:
    from backend.db import is_admin
    if not await is_admin(request.app.state.pool, user_id):
        raise HTTPException(status_code=403, detail="Admin required")
    return user_id
```

- [ ] **Step 7: Commit**

```bash
git add backend/api/ tests/test_auth.py
git commit -m "feat: FastAPI app, CORS, healthz, and initData auth validation"
```

---

### Task 9: Alerts, Analytics, Predictions routes

**Files:**
- Create: `backend/api/routes/alerts.py`
- Create: `backend/api/routes/analytics.py`
- Create: `backend/api/routes/predictions.py`
- Create: `tests/test_alerts_api.py`

- [ ] **Step 1: Create `backend/api/routes/alerts.py`**

```python
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
        query += f" ORDER BY received_at DESC LIMIT {limit} OFFSET {offset}"
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
```

- [ ] **Step 2: Create `backend/api/routes/analytics.py`**

```python
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
```

- [ ] **Step 3: Create `backend/api/routes/predictions.py`**

```python
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
```

- [ ] **Step 4: Write and run tests for alerts API**

`tests/test_alerts_api.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from tests.conftest import make_auth_header  # shared helper defined in conftest.py

# Note on test_alerts_requires_auth: FastAPI's HTTPBearer returns 403 (not 401)
# when no Authorization header is present. 401 is returned for present-but-invalid headers.

@pytest.fixture
def app(db_pool):
    import os
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
    assert resp.status_code == 403  # no auth header

async def test_alerts_returns_list(app, db_pool):
    from backend.db import insert_alert_if_new
    await insert_alert_if_new(db_pool, "api-test-1", "title", ["תל אביב"])
    headers = make_auth_header(user_id=1, bot_token="999:test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/alerts", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

```bash
pytest tests/test_alerts_api.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/alerts.py backend/api/routes/analytics.py \
        backend/api/routes/predictions.py tests/test_alerts_api.py
git commit -m "feat: alerts, analytics, and predictions API routes"
```

---

### Task 10: Admin routes

**Files:**
- Create: `backend/api/routes/admin.py`
- Create: `tests/test_admin_api.py`

- [ ] **Step 1: Create `backend/api/routes/admin.py`**

```python
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
        alerts_today = await conn.fetchval(
            "SELECT COUNT(*) FROM alerts_history WHERE received_at >= NOW() - INTERVAL '1 day'"
        )
        last_alert = await conn.fetchrow(
            "SELECT received_at FROM alerts_history ORDER BY received_at DESC LIMIT 1"
        )
    bot_enabled = await get_setting(pool, "bot_enabled")
    poll_interval = await get_setting(pool, "poll_interval_seconds")
    return {
        "subscribers": {"total": total, "active": active, "blocked": blocked, "inactive": total - active - blocked},
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
    pool = request.app.state.pool
    bot = request.app.state.bot  # set in main.py after bot creation
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT chat_id FROM subscribers WHERE active = TRUE AND blocked = FALSE"
        )
    from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfterError
    import asyncio
    for row in rows:
        try:
            await bot.send_message(chat_id=row["chat_id"], text=body.message)
        except TelegramForbiddenError:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE subscribers SET active = FALSE WHERE chat_id = $1", row["chat_id"]
                )
        except TelegramRetryAfterError as e:
            await asyncio.sleep(min(e.retry_after, 30))
            await bot.send_message(chat_id=row["chat_id"], text=body.message)
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
        count = await conn.fetchval("SELECT COUNT(*) FROM admins")
        if count <= 1:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Cannot remove last admin")
        if chat_id == admin_id:
            raise HTTPException(status_code=400, detail="Cannot remove yourself")
        await conn.execute("DELETE FROM admins WHERE chat_id = $1", chat_id)
    return {"ok": True}
```

- [ ] **Step 2: Write and run admin tests**

`tests/test_admin_api.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from tests.conftest import make_auth_header  # shared helper defined in conftest.py

async def test_admin_stats_forbidden_for_non_admin(app):
    headers = make_auth_header(user_id=9999, bot_token="999:test")  # non-admin
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/admin/stats", headers=headers)
    assert resp.status_code == 403

async def test_settings_validation_rejects_bad_interval(app, db_pool):
    from backend.db import upsert_subscriber, is_admin
    import asyncpg
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
```

```bash
pytest tests/test_admin_api.py tests/test_alerts_api.py -v
```
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/api/routes/admin.py tests/test_admin_api.py
git commit -m "feat: admin API routes with role guard and input validation"
```

---

## Phase 4: React Mini App

### Task 11: Frontend scaffold + i18n

**Files:**
- Create: `frontend/` (Vite project)
- Create: `frontend/src/i18n.ts`
- Create: `frontend/src/locales/he.json`
- Create: `frontend/src/locales/en.json`
- Create: `frontend/src/api/client.ts`

- [ ] **Step 1: Scaffold Vite project**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install react-i18next i18next axios recharts @twa-dev/sdk
npm install -D @types/node vitest @testing-library/react @testing-library/jest-dom
```

- [ ] **Step 2: Create `frontend/src/locales/he.json`**

```json
{
  "nav": {
    "history": "היסטוריה",
    "predictions": "תחזיות",
    "personal": "אישי",
    "admin": "ניהול"
  },
  "history": {
    "title": "התראות אחרונות",
    "live": "התראה פעילה כעת",
    "noAlerts": "אין התראות עדיין",
    "areas": "אזורים",
    "time": "שעה"
  },
  "predictions": {
    "title": "ניתוח דפוסים",
    "insufficientData": "אין מספיק נתונים (נדרש לפחות {{min}} התראות)",
    "peakHour": "שעת שיא",
    "peakDay": "יום שיא",
    "mostTargeted": "האזור הנפגע ביותר",
    "hourlyHeatmap": "פילוח לפי שעה",
    "weeklyChart": "פילוח לפי יום"
  },
  "personal": {
    "title": "הסטטיסטיקות שלי",
    "totalAlerts": "סה\"כ התראות",
    "matchedAlerts": "התראות שקיבלת",
    "filters": "הסינונים שלך",
    "subscriptionHistory": "היסטוריית מנוי"
  },
  "admin": {
    "title": "לוח ניהול",
    "dashboard": "סקירה",
    "subscribers": "מנויים",
    "broadcast": "שידור",
    "settings": "הגדרות",
    "admins": "מנהלים"
  },
  "common": {
    "loading": "טוען...",
    "error": "שגיאה",
    "noData": "אין מידע"
  }
}
```

- [ ] **Step 3: Create `frontend/src/locales/en.json`**

```json
{
  "nav": {
    "history": "History",
    "predictions": "Predictions",
    "personal": "Personal",
    "admin": "Admin"
  },
  "history": {
    "title": "Recent Alerts",
    "live": "Active Alert",
    "noAlerts": "No alerts yet",
    "areas": "Areas",
    "time": "Time"
  },
  "predictions": {
    "title": "Pattern Analysis",
    "insufficientData": "Insufficient data (minimum {{min}} alerts required)",
    "peakHour": "Peak Hour",
    "peakDay": "Peak Day",
    "mostTargeted": "Most Targeted Area",
    "hourlyHeatmap": "Alerts by Hour",
    "weeklyChart": "Alerts by Day"
  },
  "personal": {
    "title": "My Statistics",
    "totalAlerts": "Total Alerts",
    "matchedAlerts": "Alerts Received",
    "filters": "Your Filters",
    "subscriptionHistory": "Subscription History"
  },
  "admin": {
    "title": "Admin Panel",
    "dashboard": "Dashboard",
    "subscribers": "Subscribers",
    "broadcast": "Broadcast",
    "settings": "Settings",
    "admins": "Admins"
  },
  "common": {
    "loading": "Loading...",
    "error": "Error",
    "noData": "No data"
  }
}
```

- [ ] **Step 4: Create `frontend/src/i18n.ts`**

```typescript
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import he from "./locales/he.json";
import en from "./locales/en.json";

function detectLanguage(): string {
  const stored = localStorage.getItem("language");
  if (stored === "he" || stored === "en") return stored;
  try {
    const code = window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code ?? "";
    if (code === "iw" || code.startsWith("he")) return "he";
    if (code.startsWith("en")) return "en";
  } catch {}
  return "he";
}

const lng = detectLanguage();

i18n.use(initReactI18next).init({
  resources: { he: { translation: he }, en: { translation: en } },
  lng,
  fallbackLng: "he",
  interpolation: { escapeValue: false },
});

// Apply RTL
document.documentElement.lang = lng;
document.documentElement.dir = lng === "he" ? "rtl" : "ltr";

export default i18n;
export function setLanguage(lang: "he" | "en") {
  i18n.changeLanguage(lang);
  localStorage.setItem("language", lang);
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "he" ? "rtl" : "ltr";
}
```

- [ ] **Step 5: Create `frontend/src/api/client.ts`**

```typescript
import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

function getInitData(): string {
  return window.Telegram?.WebApp?.initData ?? "";
}

export const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use((config) => {
  const initData = getInitData();
  if (initData) {
    config.headers.Authorization = `tma ${initData}`;
  }
  return config;
});
```

- [ ] **Step 6: Write i18n test**

`frontend/src/i18n.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import i18n from "./i18n";

describe("i18n", () => {
  it("has Hebrew translations", () => {
    i18n.changeLanguage("he");
    expect(i18n.t("nav.history")).toBe("היסטוריה");
  });
  it("has English translations", () => {
    i18n.changeLanguage("en");
    expect(i18n.t("nav.history")).toBe("History");
  });
});
```

```bash
npx vitest run src/i18n.test.ts
```
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat: React frontend scaffold with i18n, RTL support, and API client"
```

---

### Task 12: App layout + navigation

**Files:**
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/components/LanguageToggle.tsx`
- Create: `frontend/src/main.tsx`

- [ ] **Step 1: Create `frontend/src/App.tsx`**

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { setLanguage } from "./i18n";
import History from "./pages/History";
import Predictions from "./pages/Predictions";
import Personal from "./pages/Personal";
import Admin from "./pages/Admin";
import LanguageToggle from "./components/LanguageToggle";
import "./App.css";

type Tab = "history" | "predictions" | "personal" | "admin";

export default function App() {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<Tab>("history");
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    window.Telegram?.WebApp?.ready();
    // Check admin status
    import("./api/client").then(({ api }) => {
      api.get("/api/admin/stats")
        .then(() => setIsAdmin(true))
        .catch(() => setIsAdmin(false));
    });
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>🚨 {i18n.language === "he" ? "פיקוד העורף" : "Pikud HaOref"}</h1>
        <LanguageToggle />
      </header>
      <nav className="tab-bar">
        {(["history", "predictions", "personal"] as Tab[]).map((t_) => (
          <button key={t_} onClick={() => setTab(t_)} className={tab === t_ ? "active" : ""}>
            {t(`nav.${t_}`)}
          </button>
        ))}
        {isAdmin && (
          <button onClick={() => setTab("admin")} className={tab === "admin" ? "active" : ""}>
            {t("nav.admin")}
          </button>
        )}
      </nav>
      <main>
        {tab === "history" && <History />}
        {tab === "predictions" && <Predictions />}
        {tab === "personal" && <Personal />}
        {tab === "admin" && isAdmin && <Admin />}
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/LanguageToggle.tsx`**

```tsx
import { useTranslation } from "react-i18next";
import { setLanguage } from "../i18n";

export default function LanguageToggle() {
  const { i18n } = useTranslation();
  const isHe = i18n.language === "he";
  return (
    <button onClick={() => setLanguage(isHe ? "en" : "he")} className="lang-toggle">
      {isHe ? "EN" : "עב"}
    </button>
  );
}
```

- [ ] **Step 3: Update `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import "./i18n";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 4: Run dev server to verify it starts**

```bash
cd frontend && npm run dev
```
Expected: Vite dev server starts on `http://localhost:5173`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/main.tsx frontend/src/components/
git commit -m "feat: Mini App layout with tab navigation and language toggle"
```

---

### Task 13: History page

**Files:**
- Create: `frontend/src/pages/History.tsx`
- Create: `frontend/src/components/AlertCard.tsx`
- Create: `frontend/src/components/LiveBanner.tsx`

- [ ] **Step 1: Create `frontend/src/components/AlertCard.tsx`**

```tsx
import { useTranslation } from "react-i18next";

interface AlertCardProps {
  title: string;
  areas: string[];
  received_at: string;
}

export default function AlertCard({ title, areas, received_at }: AlertCardProps) {
  const { t } = useTranslation();
  const time = new Date(received_at).toLocaleTimeString("he-IL");
  return (
    <div className="alert-card">
      <div className="alert-title">🚨 {title}</div>
      <div className="alert-areas">📍 {areas.join(", ")}</div>
      <div className="alert-time">🕐 {time}</div>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/LiveBanner.tsx`**

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

export default function LiveBanner() {
  const { t } = useTranslation();
  const [alert, setAlert] = useState<any>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const { data } = await api.get("/api/alerts/live");
        setAlert(data);
      } catch {}
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  if (!alert) return null;
  return (
    <div className="live-banner">
      🚨 <strong>{t("history.live")}:</strong> {alert.areas?.join(", ")}
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/pages/History.tsx`**

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import AlertCard from "../components/AlertCard";
import LiveBanner from "../components/LiveBanner";
import EmptyState from "../components/EmptyState";

export default function History() {
  const { t } = useTranslation();
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    api.get("/api/alerts", { params: { page } })
      .then(({ data }) => setAlerts(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page]);

  return (
    <div className="page">
      <h2>{t("history.title")}</h2>
      <LiveBanner />
      {loading && <p>{t("common.loading")}</p>}
      {!loading && alerts.length === 0 && <EmptyState message={t("history.noAlerts")} />}
      {alerts.map((a) => (
        <AlertCard key={a.id} {...a} />
      ))}
      <div className="pagination">
        <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>←</button>
        <span>{page}</span>
        <button disabled={alerts.length < 50} onClick={() => setPage(p => p + 1)}>→</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/components/EmptyState.tsx`**

```tsx
export default function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>;
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/History.tsx frontend/src/components/
git commit -m "feat: History page with live banner and paginated alert list"
```

---

### Task 14: Predictions + Personal pages

**Files:**
- Create: `frontend/src/pages/Predictions.tsx`
- Create: `frontend/src/pages/Personal.tsx`

- [ ] **Step 1: Create `frontend/src/pages/Predictions.tsx`**

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../api/client";
import EmptyState from "../components/EmptyState";

export default function Predictions() {
  const { t } = useTranslation();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/predictions")
      .then(({ data }) => setData(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>{t("common.loading")}</p>;
  if (!data || data.insufficient_data) {
    return <EmptyState message={t("predictions.insufficientData", { min: data?.minimum ?? 10 })} />;
  }

  return (
    <div className="page">
      <h2>{t("predictions.title")}</h2>
      {data.peak_hour && (
        <div className="stat-card">
          <div className="stat-label">{t("predictions.peakHour")}</div>
          <div className="stat-value">{data.peak_hour.hour}:00</div>
        </div>
      )}
      {data.peak_day && (
        <div className="stat-card">
          <div className="stat-label">{t("predictions.peakDay")}</div>
          <div className="stat-value">{data.peak_day.day_name}</div>
        </div>
      )}
      {data.most_targeted_area && (
        <div className="stat-card">
          <div className="stat-label">{t("predictions.mostTargeted")}</div>
          <div className="stat-value">{data.most_targeted_area.area}</div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/pages/Personal.tsx`**

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

export default function Personal() {
  const { t } = useTranslation();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/analytics/personal")
      .then(({ data }) => setData(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>{t("common.loading")}</p>;
  if (!data || data.error) return <p>{t("common.error")}</p>;

  return (
    <div className="page">
      <h2>{t("personal.title")}</h2>
      <div className="stat-card">
        <div className="stat-label">{t("personal.totalAlerts")}</div>
        <div className="stat-value">{data.total_alerts}</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">{t("personal.matchedAlerts")}</div>
        <div className="stat-value">{data.matched_alerts}</div>
      </div>
      <div className="filters-list">
        <h3>{t("personal.filters")}</h3>
        {data.filters.length === 0
          ? <p>{t("common.noData")}</p>
          : data.filters.map((f: string) => <div key={f} className="filter-chip">• {f}</div>)
        }
      </div>
      <div className="sub-history">
        <h3>{t("personal.subscriptionHistory")}</h3>
        {data.subscription_history.map((e: any, i: number) => (
          <div key={i} className="event-row">
            {e.event === "subscribed" ? "✅" : "❌"} {new Date(e.occurred_at).toLocaleDateString()}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Predictions.tsx frontend/src/pages/Personal.tsx
git commit -m "feat: Predictions and Personal analytics pages"
```

---

### Task 15: Admin panel

**Files:**
- Create: `frontend/src/pages/Admin.tsx`

- [ ] **Step 1: Create `frontend/src/pages/Admin.tsx`**

```tsx
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

type AdminTab = "dashboard" | "subscribers" | "broadcast" | "settings" | "admins";

export default function Admin() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<AdminTab>("dashboard");
  return (
    <div className="page admin-page">
      <h2>{t("admin.title")}</h2>
      <nav className="admin-tabs">
        {(["dashboard", "subscribers", "broadcast", "settings", "admins"] as AdminTab[]).map(tab_ => (
          <button key={tab_} onClick={() => setTab(tab_)} className={tab === tab_ ? "active" : ""}>
            {t(`admin.${tab_}`)}
          </button>
        ))}
      </nav>
      {tab === "dashboard" && <AdminDashboard />}
      {tab === "subscribers" && <AdminSubscribers />}
      {tab === "broadcast" && <AdminBroadcast />}
      {tab === "settings" && <AdminSettings />}
      {tab === "admins" && <AdminAdmins />}
    </div>
  );
}

function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  useEffect(() => {
    api.get("/api/admin/stats").then(({ data }) => setStats(data)).catch(() => {});
  }, []);
  if (!stats) return <p>Loading...</p>;
  return (
    <div className="dashboard">
      <div className="stat-card">Active: {stats.subscribers.active}</div>
      <div className="stat-card">Blocked: {stats.subscribers.blocked}</div>
      <div className="stat-card">Alerts today: {stats.alerts_today}</div>
      <div className="stat-card">Bot: {stats.bot_enabled ? "🟢 ON" : "🔴 OFF"}</div>
      <div className="stat-card">Poll interval: {stats.poll_interval_seconds}s</div>
    </div>
  );
}

function AdminSubscribers() {
  const [subs, setSubs] = useState<any[]>([]);
  useEffect(() => { api.get("/api/admin/subscribers").then(({ data }) => setSubs(data)); }, []);
  const block = (id: number) => api.post(`/api/admin/subscribers/${id}/block`).then(() => setSubs(s => s.map(x => x.chat_id === id ? {...x, blocked: true} : x)));
  const unblock = (id: number) => api.post(`/api/admin/subscribers/${id}/unblock`).then(() => setSubs(s => s.map(x => x.chat_id === id ? {...x, blocked: false} : x)));
  return (
    <div>
      {subs.map(s => (
        <div key={s.chat_id} className="subscriber-row">
          <span>{s.chat_id}</span>
          <span>{s.language}</span>
          <button onClick={() => s.blocked ? unblock(s.chat_id) : block(s.chat_id)}>
            {s.blocked ? "Unblock" : "Block"}
          </button>
        </div>
      ))}
    </div>
  );
}

function AdminBroadcast() {
  const [msg, setMsg] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [sent, setSent] = useState<number | null>(null);
  const send = () => {
    api.post("/api/admin/broadcast", { message: msg })
      .then(({ data }) => { setSent(data.recipients); setConfirm(false); setMsg(""); })
      .catch(() => {});
  };
  return (
    <div>
      <textarea value={msg} onChange={e => setMsg(e.target.value)} maxLength={4096} rows={5} style={{width:"100%"}} />
      <p>{msg.length}/4096</p>
      {!confirm && <button onClick={() => setConfirm(true)} disabled={!msg}>Send</button>}
      {confirm && (
        <div>
          <p>Send to all active subscribers?</p>
          <button onClick={send}>Confirm</button>
          <button onClick={() => setConfirm(false)}>Cancel</button>
        </div>
      )}
      {sent !== null && <p>Sent to {sent} subscribers</p>}
    </div>
  );
}

function AdminSettings() {
  const [settings, setSettings] = useState<any>(null);
  useEffect(() => { api.get("/api/admin/settings").then(({ data }) => setSettings(data)); }, []);
  if (!settings) return <p>Loading...</p>;
  const save = () => api.put("/api/admin/settings", settings).catch(() => {});
  return (
    <div>
      <label>Poll interval (1.0–10.0s):
        <input type="number" min={1} max={10} step={0.5}
          value={settings.poll_interval_seconds}
          onChange={e => setSettings({ ...settings, poll_interval_seconds: parseFloat(e.target.value) })} />
      </label>
      <label>Bot enabled:
        <input type="checkbox" checked={settings.bot_enabled}
          onChange={e => setSettings({ ...settings, bot_enabled: e.target.checked })} />
      </label>
      <button onClick={save}>Save</button>
    </div>
  );
}

function AdminAdmins() {
  const [admins, setAdmins] = useState<any[]>([]);
  const [newId, setNewId] = useState("");
  useEffect(() => { api.get("/api/admin/admins").then(({ data }) => setAdmins(data)); }, []);
  const add = () => api.post("/api/admin/admins", { chat_id: parseInt(newId) }).then(() => { setNewId(""); api.get("/api/admin/admins").then(({ data }) => setAdmins(data)); });
  const remove = (id: number) => api.delete(`/api/admin/admins/${id}`).then(() => setAdmins(a => a.filter(x => x.chat_id !== id)));
  return (
    <div>
      {admins.map(a => (
        <div key={a.chat_id} className="admin-row">
          <span>{a.chat_id}</span>
          <button onClick={() => remove(a.chat_id)}>Remove</button>
        </div>
      ))}
      <input value={newId} onChange={e => setNewId(e.target.value)} placeholder="Telegram user ID" />
      <button onClick={add} disabled={!newId}>Add Admin</button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Admin.tsx
git commit -m "feat: Admin panel with dashboard, subscribers, broadcast, settings, and admins tabs"
```

---

### Task 16: Deployment setup

**Files:**
- Create: `frontend/vite.config.ts` (update)
- Verify: `railway.toml`

- [ ] **Step 1: Update `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
  },
});
```

- [ ] **Step 2: Create `frontend/src/setupTests.ts`**

```typescript
import "@testing-library/jest-dom";
// Mock Telegram WebApp
(window as any).Telegram = {
  WebApp: {
    ready: () => {},
    initData: "",
    initDataUnsafe: { user: { id: 1, language_code: "en" } },
  },
};
```

- [ ] **Step 3: Build frontend and verify**

```bash
cd frontend && npm run build
```
Expected: Build completes with no errors, `dist/` created.

- [ ] **Step 4: Run all backend tests**

```bash
cd .. && pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 5: Final commit**

```bash
git add frontend/vite.config.ts frontend/src/setupTests.ts
git commit -m "chore: deployment configuration and test setup finalized"
```

---

## Deployment Checklist

- [ ] Create Railway project, provision PostgreSQL add-on
- [ ] Set Railway env vars: `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `MINI_APP_URL`, `SUPERADMIN_CHAT_ID`
- [ ] Push to GitHub → Railway auto-deploys
- [ ] Verify `/healthz` returns `{"status": "ok"}`
- [ ] Create Vercel project, set root to `frontend/`, set `VITE_API_URL` to Railway URL
- [ ] Vercel deploys → copy URL → update `MINI_APP_URL` in Railway
- [ ] Run `/setmenubutton` with @BotFather to register the Mini App URL
- [ ] Test: send `/start` to the bot, tap the Mini App button
