# Pikud HaOref Telegram Alert Bot — Design Spec

**Date:** 2026-03-21
**Status:** Approved

---

## Overview

A public Telegram bot that delivers real-time Pikud HaOref rocket/missile alerts to subscribers, with an embedded **Telegram Mini App** providing alert history, pattern-based predictions, personal analytics, and a full admin panel. Fully bilingual: Hebrew (RTL) and English.

---

## Goals

- Deliver Pikud HaOref alerts with minimal latency (~1-2 seconds) via Telegram
- Public subscription model with optional per-user area filtering
- Telegram Mini App with four sections: Live/History, Predictions, Personal Analytics, Admin Panel
- Admin panel supporting multiple admins (managed via DB), full bot control
- Full bilingual support: Hebrew (RTL) and English — bot messages and Mini App UI
- Always-on deployment on Railway Hobby plan

---

## Non-Goals

- No native mobile app — Mini App runs inside Telegram
- No group chat support (personal chats only)
- No ML/AI predictions — pattern-based statistical analysis only
- No paid tiers
- No languages beyond Hebrew and English

---

## Architecture

```text
┌─────────────────────────────────┐     ┌──────────────────────────┐
│  Railway: Python Service         │     │  Vercel: React Mini App   │
│                                  │     │                           │
│  ┌──────────┐  ┌──────────────┐  │     │  ┌─────────────────────┐  │
│  │  aiogram │  │   FastAPI    │◄─┼─────┼─►│  Telegram WebApp    │  │
│  │   bot    │  │   HTTP API   │  │     │  │  (React + Vite)     │  │
│  └────┬─────┘  └──────┬───────┘  │     │  └─────────────────────┘  │
│       │               │          │     └──────────────────────────┘
│  ┌────▼───────────────▼───────┐  │
│  │     Shared asyncio loop     │  │
│  └────────────┬────────────────┘  │
│               │                   │
│  ┌────────────▼────────────────┐  │
│  │         PostgreSQL           │  │
│  │  (Railway managed add-on)    │  │
│  └─────────────────────────────┘  │
└─────────────────────────────────┘
```

**Python Service (Railway):** One process runs three concurrent asyncio tasks:

1. **Oref Poller** — polls API every 1.5s, deduplicates in-memory, puts to `asyncio.Queue(maxsize=1)`. If the queue is full (Notifier is still processing), the new alert replaces the queued one (avoids flood during active barrages).
2. **Notifier** — consumes from the queue, persists to `alerts_history`, fans out Telegram messages to all active subscribers.
3. **FastAPI server** — launched via `uvicorn.Server` with an asyncio-compatible `Config` (not `uvicorn.run`), sharing the same event loop. Listens on `$PORT` (Railway-injected), falling back to `API_PORT`.

**Mini App (Vercel):** React + Vite SPA. Opens via a WebApp button in the bot chat. Authenticates all API requests via Telegram `initData`.

**Railway note:** Hobby plan ($5/mo) is required for always-on behavior. The free tier sleeps on idle, which would break continuous polling.

---

## File Structure

```text
pakad/
├── backend/
│   ├── main.py              — entry point, starts all asyncio tasks
│   ├── oref_poller.py       — Oref API polling + deduplication
│   ├── notifier.py          — Telegram fan-out
│   ├── bot.py               — aiogram bot commands
│   ├── api/
│   │   ├── app.py           — FastAPI app instance + CORS middleware
│   │   ├── auth.py          — Telegram initData validation (incl. auth_date check)
│   │   ├── routes/
│   │   │   ├── alerts.py    — alert history endpoints
│   │   │   ├── analytics.py — global + personal analytics
│   │   │   ├── predictions.py — pattern-based predictions
│   │   │   └── admin.py     — admin-only endpoints
│   ├── db.py                — async PostgreSQL via asyncpg
│   ├── areas.py             — fallback canonical Oref area list (used if DB areas table is empty)
│   ├── messages.py          — bilingual bot message templates (he/en)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── History.tsx       — alert history + live feed
│   │   │   ├── Predictions.tsx   — pattern analysis
│   │   │   ├── Personal.tsx      — personal analytics
│   │   │   └── Admin.tsx         — admin panel (admin-only)
│   │   ├── components/
│   │   ├── locales/
│   │   │   ├── he.json           — Hebrew UI strings
│   │   │   └── en.json           — English UI strings
│   │   └── api/              — typed API client
│   ├── package.json
│   └── vite.config.ts
└── railway.toml
```

---

## Data Model

### Table: `subscribers`

| column          | type        | notes                             |
| --------------- | ----------- | --------------------------------- |
| `chat_id`       | BIGINT PK   | Telegram chat ID                  |
| `subscribed_at` | TIMESTAMPTZ | Timestamp of last `/start`        |
| `active`        | BOOLEAN     | False after `/stop`               |
| `blocked`       | BOOLEAN     | True if admin-blocked             |
| `language`      | TEXT        | `'he'` or `'en'`, default `'he'`  |

**Re-subscription:** `/start` after `/stop` sets `active = true` and updates `subscribed_at`.

### Table: `subscription_events`

| column       | type        | notes                                    |
| ------------ | ----------- | ---------------------------------------- |
| `id`         | SERIAL PK   |                                          |
| `chat_id`    | BIGINT FK   | references subscribers                   |
| `event`      | TEXT        | `'subscribed'` or `'unsubscribed'`       |
| `occurred_at`| TIMESTAMPTZ |                                          |

Appended on every `/start` and `/stop`. Used to power the subscription history view in Personal Analytics.

### Table: `subscriber_filters`

| column    | type      | notes                          |
| --------- | --------- | ------------------------------ |
| `chat_id` | BIGINT FK | Composite PK with `area`       |
| `area`    | TEXT FK   | References `areas.name`; composite PK |

Max 10 filters per user. Insert uses `ON CONFLICT DO NOTHING`. The bot checks count before inserting and returns an error message if the limit is already reached (no silent failure). When an area is deleted from the `areas` table, its rows in `subscriber_filters` are cascade-deleted.

### Table: `areas`

| column       | type      | notes                                |
| ------------ | --------- | ------------------------------------ |
| `name`       | TEXT PK   | Hebrew area name                     |
| `added_at`   | TIMESTAMPTZ |                                    |

Seeded from `areas.py` on first run (INSERT IF NOT EXISTS). Admin panel can add/remove rows. `areas.py` serves as fallback if the table is empty.

### Table: `alerts_history`

| column       | type        | notes                             |
| ------------ | ----------- | --------------------------------- |
| `id`         | SERIAL PK   |                                   |
| `oref_id`    | TEXT UNIQUE | Alert ID from Oref API            |
| `title`      | TEXT        | Alert type title (Hebrew)         |
| `areas`      | TEXT[]      | Array of affected area names      |
| `received_at`| TIMESTAMPTZ | When the bot first detected it    |

`oref_id UNIQUE` serves as the **persistent dedup guard**: before fan-out, the Notifier attempts `INSERT ... ON CONFLICT DO NOTHING` and checks the rows-affected count. If 0 (already exists), fan-out is skipped. This prevents re-notification when `last_alert_id` resets after a crash.

### Table: `admins`

| column    | type        | notes                          |
| --------- | ----------- | ------------------------------ |
| `chat_id` | BIGINT PK   | Telegram user ID               |
| `added_by`| BIGINT      | `chat_id` of admin who added   |
| `added_at`| TIMESTAMPTZ |                                |

Seeded with `SUPERADMIN_CHAT_ID` on first run using `INSERT IF NOT EXISTS` — safe on restart.

### Table: `bot_settings`

| column  | type    | notes                                    |
| ------- | ------- | ---------------------------------------- |
| `key`   | TEXT PK | Setting name                             |
| `value` | TEXT    | Value (cast on read per known key types) |

Initial rows: `poll_interval_seconds = '1.5'`, `bot_enabled = 'true'`.

**Settings precedence:** `POLL_INTERVAL_SECONDS` env var seeds the DB row on first run only. At runtime, the Notifier reads `poll_interval_seconds` from the DB. Admin panel changes update the DB row and take effect on the next poll cycle. The env var is never re-read after startup.

---

## Bot Commands

| command            | behavior                                                     |
| ------------------ | ------------------------------------------------------------ |
| `/start`           | Subscribe; shows welcome + Mini App button; logs event       |
| `/stop`            | Unsubscribe; logs event                                      |
| `/filter <area>`   | Add area filter; validates against `areas` table; returns error if at limit (10) |
| `/filters`         | List current active filters                                  |
| `/clearfilters`    | Remove all filters                                           |
| `/areas`           | List all valid area names from `areas` table                 |
| `/status`          | Show subscription status and current filters                 |
| `/app`             | Re-send Mini App launch button                               |
| `/language <code>` | Set language: `he` or `en`; updates `subscribers.language`  |

The Mini App is opened via a Telegram `WebApp` inline keyboard button sent on `/start` and `/app`.

---

## Mini App — Sections

### 1. History & Live Feed

- List of recent alerts from `alerts_history`, newest first
- Each row: time, areas affected, alert type
- Live: polls `GET /api/alerts/live` every 3 seconds; displays active alert banner if present
- An alert is "live" for 60 seconds after `received_at`; after that, `/api/alerts/live` returns `null`
- Filters: by date range, by area
- Empty state: "No alerts recorded yet" if table is empty

### 2. Predictions (Pattern Analysis)

Statistical insights from `alerts_history`. All derived from aggregate SQL queries — no ML.

- **Time-of-day heatmap** — alert frequency by hour of day
- **Day-of-week chart** — alert frequency by weekday
- **Area frequency ranking** — most-targeted areas in selected time window
- **Rolling 7-day trend** — alert count per day for the past week

Empty state: shown when `alerts_history` has fewer than 10 records (insufficient data message displayed instead of charts).

### 3. Personal Analytics

Requires authenticated user (validated `initData`):

- Total alerts received
- Alerts matched vs. total (filter effectiveness ratio)
- Most frequent alert areas in user's subscription
- Subscription history (timeline from `subscription_events`)

### 4. Admin Panel

Visible only to users whose `chat_id` is in the `admins` table (checked on page load and per request).

**Dashboard tab:** subscriber counts (active/inactive/blocked), alerts delivered today/week/all-time, bot on/off status, current poll interval, last alert timestamp.

**Subscribers tab:** paginated list, block/unblock, search by chat ID.

**Broadcast tab:** text input (max 4096 characters, Telegram limit), confirmation step before sending.

**Settings tab:** adjust poll interval (1.0–10.0s — validated server-side on `PUT /api/admin/settings`; out-of-range values return 422), toggle bot on/off. Toggling off completes the current in-progress fan-out batch before stopping; it does not abort mid-fan-out. Manage areas (add/remove rows from `areas` table).

**Admins tab:** list admins, add by Telegram user ID, remove (cannot remove self if last admin).

---

## REST API

All endpoints except `GET /healthz` require `Authorization: tma <initData>`. `/healthz` is explicitly exempt — it is called by Railway with no auth header. Backend validates HMAC-SHA256 signature and checks `auth_date` is not older than **1 hour** (replay attack prevention). Requests with expired `auth_date` return 401.

### Alerts

| method | path | description |
| ------ | ---- | ----------- |
| GET | `/api/alerts` | Paginated history (`?page`, `?area`, `?from`, `?to`) |
| GET | `/api/alerts/live` | Active alert (within 60s of `received_at`) or `null` |

### Analytics

| method | path | description |
| ------ | ---- | ----------- |
| GET | `/api/analytics/global` | Heatmaps, trends, top areas |
| GET | `/api/analytics/personal` | Per-user stats (identity from initData) |

### Predictions

| method | path | description |
| ------ | ---- | ----------- |
| GET | `/api/predictions` | Pattern insights (returns empty-state flag if < 10 records) |

### Admin (admin role required)

| method | path | description |
| ------ | ---- | ----------- |
| GET | `/api/admin/stats` | Dashboard stats |
| GET | `/api/admin/subscribers` | Paginated subscriber list |
| POST | `/api/admin/subscribers/:chat_id/block` | Block subscriber |
| POST | `/api/admin/subscribers/:chat_id/unblock` | Unblock subscriber |
| POST | `/api/admin/broadcast` | Broadcast message (max 4096 chars) |
| GET | `/api/admin/settings` | Get bot settings |
| PUT | `/api/admin/settings` | Update settings |
| GET | `/api/admin/areas` | List areas |
| POST | `/api/admin/areas` | Add area |
| DELETE | `/api/admin/areas/:name` | Remove area (cascades subscriber_filters) |
| GET | `/api/admin/admins` | List admins |
| POST | `/api/admin/admins` | Add admin by chat_id |
| DELETE | `/api/admin/admins/:chat_id` | Remove admin |

**CORS:** FastAPI is configured with `CORSMiddleware` allowing only `CORS_ORIGINS` (defaults to `MINI_APP_URL`). All other origins are rejected.

---

## Authentication & Authorization

**Telegram Mini App auth flow:**

1. Frontend reads `window.Telegram.WebApp.initData` on load
2. All API requests send `Authorization: tma <initData>` header
3. `auth.py` validates:
   - HMAC-SHA256 signature using `TELEGRAM_BOT_TOKEN`
   - `auth_date` is within the last 3600 seconds (1 hour)
4. Extracts `user.id` from validated `initData` → request identity
5. Admin endpoints check `user.id` against `admins` table

**Note on `initDataUnsafe`:** The Mini App uses `WebApp.initDataUnsafe.user.language_code` only as a UI default hint — never for authentication or identity. All auth uses the verified `initData` string.

---

## Internationalization (i18n)

### Bot Messages

All bot responses rendered from templates in `messages.py`, keyed by `language`. The user's `language` column is read from DB on each response. Default: `'he'`.

Alert message — English variant:

```text
🚨 *Rocket & Missile Fire*

📍 *Areas:* תל אביב, רמת גן
🕐 *Time:* 14:32:07

Enter a protected space immediately!
```

Area names are always Hebrew (from Oref API) in both language variants.

### Mini App Frontend

- **`react-i18next`** for all UI strings
- `locales/he.json` and `locales/en.json`
- Language stored in `localStorage`; persists across sessions
- Initial default detection order:
  1. `localStorage` value (if previously set)
  2. `WebApp.initDataUnsafe.user.language_code` → mapped: `'iw'` → `'he'`, `'en-*'` → `'en'`, unknown → `'he'`
  3. Fallback: `'he'`
- Language toggle button in Mini App header
- Hebrew → full RTL layout (`dir="rtl"` on `<html>` element, `direction: rtl` on root CSS)

---

## Alert Message Format

Hebrew:

```text
🚨 *ירי רקטות וטילים*

📍 *אזורים:* תל אביב, רמת גן
🕐 *שעה:* 14:32:07

היכנסו למרחב המוגן מיד!
```

Sent with `parse_mode=ParseMode.MARKDOWN` plus an inline keyboard button to open the Mini App.

---

## Oref API

- **Endpoint:** `GET https://www.oref.org.il/WarningMessages/alert/alerts.json`
- **Required headers:** `Referer: https://www.oref.org.il/`, `X-Requested-With: XMLHttpRequest`
- **Active alert response:**

```json
{
  "id": "133413341334",
  "cat": "1",
  "title": "ירי רקטות וטילים",
  "data": ["תל אביב", "רמת גן"],
  "desc": "היכנסו למרחב המוגן מיד"
}
```

- **No active alert:** empty string or `{}` — skip
- **In-memory dedup:** `last_alert_id: str | None = None`. First response seeds it without dispatching. Changed ID → put to queue. Persistent dedup (crash-safe) via `oref_id UNIQUE` in `alerts_history` (see Data Model).

---

## Error Handling

| scenario | behavior |
| -------- | -------- |
| Oref non-200 or timeout (5s) | Log warning, skip cycle |
| Malformed/empty Oref JSON | Treat as no alert, skip |
| `oref_id` already in DB (crash restart) | Skip fan-out (persistent dedup) |
| `TelegramForbiddenError` | Set `active = false`, continue fan-out |
| `TelegramRetryAfterError` | Await retry-after (capped at 30s), resend; continue fan-out after |
| Other Telegram send error | Log, skip that subscriber, continue fan-out |
| Bot paused (`bot_enabled = false`) | Completes current fan-out batch, then pauses polling |
| Invalid or expired `initData` | Return 401 |
| Non-admin on admin endpoint | Return 403 |
| Broadcast fan-out error | Same rules as alert fan-out: `ForbiddenError` → set `active=false`; `RetryAfterError` → honour delay; other errors → log and continue |
| `asyncpg` connection loss | Process crashes; Railway auto-restarts |
| Process crash | Railway restarts; in-memory `last_alert_id` resets; DB dedup prevents re-notification |

---

## Configuration

| variable | description | default |
| -------- | ----------- | ------- |
| `TELEGRAM_BOT_TOKEN` | From @BotFather | required |
| `DATABASE_URL` | PostgreSQL connection string | required |
| `MINI_APP_URL` | Vercel deployment URL | required |
| `SUPERADMIN_CHAT_ID` | Initial admin Telegram user ID | required |
| `POLL_INTERVAL_SECONDS` | Seeds DB on first run (1.0–10.0) | `1.5` |
| `CORS_ORIGINS` | Comma-separated allowed origins | defaults to `MINI_APP_URL` |
| `API_PORT` | Fallback port if `$PORT` not set | `8000` |

FastAPI binds to `$PORT` (Railway-injected) first; falls back to `API_PORT`.

---

## `railway.toml`

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python backend/main.py"
restartPolicyType = "always"
healthcheckPath = "/healthz"
healthcheckTimeout = 10
```

FastAPI exposes `GET /healthz` returning `{"status": "ok"}` — used by Railway to verify the process is alive.

---

## Dependencies

**Backend:**

```text
aiogram==3.x
fastapi
uvicorn
asyncpg
aiohttp
```

**Frontend:**

```text
react
vite
@twa-dev/sdk
recharts
axios
react-i18next
i18next
```

---

## Deployment

**Backend (Railway — Hobby plan):**

1. Push repo to GitHub, connect to Railway
2. Provision PostgreSQL add-on; Railway sets `DATABASE_URL` automatically
3. Set all required env vars in Railway dashboard
4. Railway runs `python backend/main.py`; health check confirms startup

**Frontend (Vercel):**

1. Connect same GitHub repo, set root directory to `frontend/`
2. Set `VITE_API_URL` env var to the Railway service public URL
3. Vercel auto-deploys on push to `main`
4. Copy the Vercel deployment URL → set as `MINI_APP_URL` in Railway
5. Register Mini App URL with @BotFather: `/setmenubutton` → set URL to Vercel deployment
