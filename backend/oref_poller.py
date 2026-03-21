import asyncio
import logging
import aiohttp
import asyncpg
from typing import Optional

logger = logging.getLogger(__name__)

OREF_URL = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
OREF_HEADERS = {
    "Referer": "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
}

class OrefPoller:
    def __init__(self, queue: asyncio.Queue, interval: float = 1.5, pool: Optional[asyncpg.Pool] = None):
        self._queue = queue
        self._interval = interval
        self._pool = pool
        self._last_alert_id: Optional[str] = None

    async def _get_interval(self) -> float:
        if self._pool is None:
            return self._interval
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT value FROM bot_settings WHERE key = 'poll_interval_seconds'"
                )
            if row:
                return float(row["value"])
        except Exception:
            pass
        return self._interval

    async def run(self) -> None:
        """Production entry point — uses a single persistent aiohttp session."""
        async with aiohttp.ClientSession() as session:
            while True:
                await self._poll_once(session)
                interval = await self._get_interval()
                await asyncio.sleep(interval)

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
