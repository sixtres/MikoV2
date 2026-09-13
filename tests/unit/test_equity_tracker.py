import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.storage.equity_tracker import EquityTracker, EquityTrackerConfig
from src.storage.mark_price_cache import MarkPriceCache


def test_mark_cache_defaults():
    c = MarkPriceCache()
    assert c.size() == 0


@pytest.mark.asyncio
async def test_mark_cache_update_get():
    c = MarkPriceCache()
    await c.update("BTC_USDT", 50000.0, 1000)
    assert await c.get("BTC_USDT") == 50000.0
    res = await c.get_with_ts("BTC_USDT")
    assert res == (50000.0, 1000)


@pytest.mark.asyncio
async def test_mark_cache_missing_returns_none():
    c = MarkPriceCache()
    assert await c.get("NONE") is None
    assert await c.get_with_ts("NONE") is None


@pytest.mark.asyncio
async def test_mark_cache_handle_event():
    c = MarkPriceCache()
    ok = await c.handle_event(
        {"type": "mark_price", "symbol": "BTC_USDT", "price": 50000.0, "ts_ms": 1000}
    )
    assert ok is True
    assert await c.get("BTC_USDT") == 50000.0


@pytest.mark.asyncio
async def test_mark_cache_handle_event_wrong_type():
    c = MarkPriceCache()
    ok = await c.handle_event({"type": "other", "symbol": "BTC_USDT"})
    assert ok is False
    assert c.size() == 0


def test_equity_config_defaults():
    cfg = EquityTrackerConfig()
    assert cfg.timer_interval_s == 60.0
    assert cfg.base_balance == 1000.0


def _make_tracker(rows=None):
    cfg = EquityTrackerConfig(base_balance=1000.0)
    sqlite = MagicMock()
    sqlite.list_open_positions = AsyncMock(return_value=rows or [])
    sqlite.insert_equity_snapshot = AsyncMock(return_value=None)
    cache = MarkPriceCache()
    lock = asyncio.Lock()
    return EquityTracker(cfg, sqlite, cache, lock), sqlite, cache


@pytest.mark.asyncio
async def test_compute_snapshot_empty_positions():
    tr, _, _ = _make_tracker()
    snap = await tr.compute_snapshot()
    assert snap is not None
    assert snap["open_positions"] == 0
    assert snap["unrealized_pnl"] == 0.0
    assert snap["equity"] == 1000.0


@pytest.mark.asyncio
async def test_compute_snapshot_long_pnl():
    # position row: id, symbol, side, opened_at_ms, avg, qty_open,
    #               qty_remaining, ...
    rows = [
        ("pos1", "BTC_USDT", "LONG", 1000, 100.0, 0.5, 0.5, None, None, 0, 0, 0, "IN_TOP5", 0, 0),
    ]
    tr, _, cache = _make_tracker(rows)
    await cache.update("BTC_USDT", 110.0, 2000)
    snap = await tr.compute_snapshot()
    assert snap["open_positions"] == 1
    # (110 - 100) * 0.5 = 5
    assert abs(snap["unrealized_pnl"] - 5.0) < 1e-9
    assert abs(snap["equity"] - 1005.0) < 1e-9


@pytest.mark.asyncio
async def test_compute_snapshot_short_pnl():
    rows = [
        ("pos1", "BTC_USDT", "SHORT", 1000, 100.0, 0.5, 0.5, None, None, 0, 0, 0, "IN_TOP5", 0, 0),
    ]
    tr, _, cache = _make_tracker(rows)
    await cache.update("BTC_USDT", 95.0, 2000)
    snap = await tr.compute_snapshot()
    # (100 - 95) * 0.5 = 2.5
    assert abs(snap["unrealized_pnl"] - 2.5) < 1e-9


@pytest.mark.asyncio
async def test_compute_snapshot_missing_mark_skips():
    rows = [
        ("pos1", "BTC_USDT", "LONG", 1000, 100.0, 0.5, 0.5, None, None, 0, 0, 0, "IN_TOP5", 0, 0),
    ]
    tr, _, _ = _make_tracker(rows)
    # cache empty -> skip position
    snap = await tr.compute_snapshot()
    assert snap["open_positions"] == 1
    assert snap["unrealized_pnl"] == 0.0


@pytest.mark.asyncio
async def test_snapshot_once_writes_db():
    tr, sqlite, _ = _make_tracker()
    ok = await tr.snapshot_once()
    assert ok is True
    sqlite.insert_equity_snapshot.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_position_close_updates_realized():
    tr, sqlite, _ = _make_tracker()
    await tr.on_position_close(realized_pnl=15.0)
    assert tr.get_realized_today() == 15.0
    sqlite.insert_equity_snapshot.assert_awaited()


@pytest.mark.asyncio
async def test_drawdown_tracks_peak():
    tr, _, cache = _make_tracker()
    # Force high peak
    tr._peak_equity = 1100.0
    snap = await tr.compute_snapshot()
    assert snap["drawdown_pct"] > 0


@pytest.mark.asyncio
async def test_run_loop_stops_on_shutdown():
    tr, _, _ = _make_tracker()
    shutdown = asyncio.Event()

    async def has_open():
        return False

    task = asyncio.create_task(tr.run_loop(shutdown, has_open))
    await asyncio.sleep(0.05)
    shutdown.set()
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done()


def test_no_global_state():
    assert not hasattr(EquityTracker, "_realized_today")
    assert not hasattr(MarkPriceCache, "_prices")