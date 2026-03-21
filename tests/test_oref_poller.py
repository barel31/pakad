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

async def test_timeout_is_handled_gracefully():
    queue = asyncio.Queue(maxsize=1)
    poller = OrefPoller(queue=queue, interval=0.1)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(side_effect=asyncio.TimeoutError()),
        __aexit__=AsyncMock(return_value=False),
    ))
    await poller._poll_once(mock_session)  # must not raise
    assert queue.empty()
