"""
Tests for src.data_layer.mexc_ws
MEXC Futures WS depth client (no real network in tests).
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data_layer.mexc_ws import (
    DEFAULT_DEAD_TIMEOUT_S,
    DEFAULT_PING_INTERVAL_S,
    MEXC_WS_URL,
    MEXCWSClient,
)


def _make_client(handler=None):
    if handler is None:
        handler = AsyncMock()
    return MEXCWSClient(symbols=["BTC_USDT", "ETH_USDT"], on_depth=handler), handler


def test_defaults():
    c, _ = _make_client()
    assert c.url == MEXC_WS_URL
    assert c.ping_interval_s == DEFAULT_PING_INTERVAL_S
    assert c.dead_timeout_s == DEFAULT_DEAD_TIMEOUT_S
    assert c.symbols == ["BTC_USDT", "ETH_USDT"]


def test_no_global_state():
    assert not hasattr(MEXCWSClient, "_ws")
    assert not hasattr(MEXCWSClient, "_session")


@pytest.mark.asyncio
async def test_handle_push_depth_dispatches():
    c, handler = _make_client()
    msg = {
        "channel": "push.depth",
        "symbol": "BTC_USDT",
        "data": {
            "cts": 1234567890,
            "asks": [[100.0, 1.0, 1]],
            "bids": [[99.0, 2.0, 2]],
            "version": 1000,
        },
        "ts": 1234567895,
    }
    await c._handle_message(msg)
    handler.assert_awaited_once()
    args, _ = handler.await_args
    assert args[0] == "BTC_USDT"
    assert args[1]["version"] == 1000


@pytest.mark.asyncio
async def test_handle_ignores_pong_channel():
    c, handler = _make_client()
    await c._handle_message({"channel": "pong", "data": 12345})
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_ignores_missing_symbol():
    c, handler = _make_client()
    await c._handle_message({"channel": "push.depth", "data": {"version": 1}})
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_ignores_missing_data():
    c, handler = _make_client()
    await c._handle_message({"channel": "push.depth", "symbol": "BTC_USDT"})
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_callback_exception_does_not_crash():
    async def bad_handler(symbol, data):
        raise RuntimeError("boom")

    c = MEXCWSClient(symbols=["BTC_USDT"], on_depth=bad_handler)
    msg = {
        "channel": "push.depth",
        "symbol": "BTC_USDT",
        "data": {"version": 1, "bids": [], "asks": []},
    }
    # must not raise
    await c._handle_message(msg)


@pytest.mark.asyncio
async def test_handle_raw_valid_json():
    c, handler = _make_client()
    raw = json.dumps(
        {
            "channel": "push.depth",
            "symbol": "BTC_USDT",
            "data": {"version": 7, "bids": [[1.0, 1.0, 1]], "asks": []},
        }
    )
    await c._handle_raw(raw)
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_raw_invalid_json_silent():
    c, handler = _make_client()
    await c._handle_raw("not json {")
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_cancels_tasks():
    c, _ = _make_client()

    # Fake internal tasks
    async def slow():
        await asyncio.sleep(10)

    c._read_task = asyncio.create_task(slow())
    c._ping_task = asyncio.create_task(slow())
    c._running = True
    c._session = MagicMock()
    c._session.close = AsyncMock()
    c._ws = MagicMock()
    c._ws.close = AsyncMock()

    await c.close()
    assert c._read_task is None
    assert c._ping_task is None
    assert c._ws is None
    assert c._session is None


@pytest.mark.asyncio
async def test_close_idempotent():
    c, _ = _make_client()
    await c.close()
    await c.close()
    assert c._ws is None
    assert c._session is None