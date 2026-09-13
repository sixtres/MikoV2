"""
Emergency close end-to-end integration tests.
Y-260 slippage, Y-283 FLIP, Y-295 lock disi, Y-341 persist, Y-350 hierarchy, Y-351 single-flight.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.emergency.close import EmergencyCloser, EmergencyCloserConfig
from src.execution.order_manager import OrderManager, OrderManagerConfig


def _make_closer(rest=None, rest_exc=None, direct_result=...):
    cfg = EmergencyCloserConfig(reduce_only=True, max_retry=1, leverage=5, min_lot=0.001)

    if rest is None:
        rest = MagicMock()
        if rest_exc is not None:
            rest.post_market_order = AsyncMock(side_effect=rest_exc)
        else:
            rest.post_market_order = AsyncMock(
                return_value={"status": "ok", "slippage": 0.0}
            )
        if direct_result is ...:
            direct_result = {"status": "forced"}
        rest._direct_market_post = AsyncMock(return_value=direct_result)

    sqlite = MagicMock()
    sqlite.execute_wal = AsyncMock(return_value=None)
    sealed = MagicMock()
    flush = MagicMock()
    flush.suspend = MagicMock()
    flush.resume = MagicMock()
    tasks = {}
    closer = EmergencyCloser(cfg, rest, sqlite, sealed, flush, tasks)
    return closer, rest, flush, sqlite, tasks


@pytest.mark.asyncio
async def test_e2e_close_success_flow():
    closer, rest, flush, sqlite, tasks = _make_closer()
    result = await closer.emergency_close_with_retry("BTCUSDT")

    assert result == "CLOSED"
    rest.post_market_order.assert_awaited()
    flush.suspend.assert_called_once()
    flush.resume.assert_called_once()
    sqlite.execute_wal.assert_awaited()
    await asyncio.sleep(0.01)
    assert "BTCUSDT" not in tasks


@pytest.mark.asyncio
async def test_e2e_pacer_full_fallback_direct():
    closer, rest, flush, sqlite, tasks = _make_closer(
        rest_exc=RuntimeError("CRITICAL pacer full")
    )
    result = await closer.emergency_close_with_retry("BTCUSDT")

    assert result == "FORCE_LIQUIDATED_BY_SYSTEM"
    rest._direct_market_post.assert_awaited()
    flush.resume.assert_called_once()


@pytest.mark.asyncio
async def test_e2e_direct_market_none_failure():
    closer, rest, flush, sqlite, tasks = _make_closer(
        rest_exc=RuntimeError("CRITICAL pacer full"),
        direct_result=None,
    )
    result = await closer.emergency_close_with_retry("BTCUSDT")

    assert result == "EMERGENCY_FAILED_POSITION_OPEN"
    # flush must still resume even on failure
    flush.resume.assert_called_once()


@pytest.mark.asyncio
async def test_e2e_flush_suspend_resume_on_exception():
    """Even if rest raises unexpected exception, flush resumes."""
    closer, rest, flush, sqlite, tasks = _make_closer(
        rest_exc=Exception("unexpected")
    )
    result = await closer.emergency_close_with_retry("BTCUSDT")
    assert result == "EMERGENCY_FAILED_POSITION_OPEN"
    flush.suspend.assert_called_once()
    flush.resume.assert_called_once()


@pytest.mark.asyncio
async def test_e2e_single_flight_same_symbol():
    closer, rest, flush, sqlite, tasks = _make_closer()
    t1 = asyncio.create_task(closer.emergency_close_with_retry("BTCUSDT"))
    t2 = asyncio.create_task(closer.emergency_close_with_retry("BTCUSDT"))
    r1, r2 = await asyncio.gather(t1, t2)

    assert r1 == "CLOSED"
    assert r2 == "CLOSED"
    # only one post, second call returns same task
    assert rest.post_market_order.await_count == 1
    assert flush.suspend.call_count == 1


@pytest.mark.asyncio
async def test_e2e_task_pop_after_done():
    closer, rest, flush, sqlite, tasks = _make_closer()
    await closer.emergency_close_with_retry("BTCUSDT")
    await asyncio.sleep(0.02)
    assert "BTCUSDT" not in tasks


@pytest.mark.asyncio
async def test_e2e_slippage_force_liq():
    closer, rest, flush, sqlite, tasks = _make_closer()
    rest.post_market_order = AsyncMock(
        return_value={"status": "ok", "slippage": 0.5}
    )
    result = await closer.emergency_close_with_retry("BTCUSDT")
    assert result == "FORCE_LIQUIDATED_BY_SYSTEM"


def test_e2e_slippage_5x():
    closer, *_ = _make_closer()
    assert abs(closer.leverage_adjusted_slippage() - 0.02) < 1e-9


def test_e2e_slippage_20x():
    cfg = EmergencyCloserConfig(leverage=20)
    closer = EmergencyCloser(cfg, MagicMock(), MagicMock(), MagicMock(), MagicMock(), {})
    assert abs(closer.leverage_adjusted_slippage() - 0.005) < 1e-9


@pytest.mark.asyncio
async def test_e2e_order_manager_flip_then_emergency_outside_lock():
    """OrderManager FLIP detection calls emergency_close OUTSIDE fill_lock."""
    cfg = OrderManagerConfig(max_retry=3, leverage=5, min_lot=0.001)
    fill_lock = asyncio.Lock()
    sqlite_writer = MagicMock()
    sqlite_writer.fetch = AsyncMock(return_value=[])
    sqlite_writer.get_version = AsyncMock(return_value=0)
    sqlite_writer.update_position_versioned = AsyncMock(return_value=True)
    sealed = MagicMock()
    rest = MagicMock()
    lock_during_close = []

    async def fake_close(order_id):
        lock_during_close.append(fill_lock.locked())

    rest.emergency_close = AsyncMock(side_effect=fake_close)

    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed, rest)
    om._filled_by_order["oid1"] = 1.0

    await om.on_fill_event("oid1", -1.0, 100.0, 123, "pos1")

    rest.emergency_close.assert_awaited()
    assert lock_during_close == [False], "emergency_close fill_lock ile cagrildi"


@pytest.mark.asyncio
async def test_e2e_multi_symbol_independent():
    closer, rest, flush, sqlite, tasks = _make_closer()
    r1 = await closer.emergency_close_with_retry("BTCUSDT")
    r2 = await closer.emergency_close_with_retry("ETHUSDT")
    assert r1 == "CLOSED"
    assert r2 == "CLOSED"
    assert rest.post_market_order.await_count == 2
    assert flush.suspend.call_count == 2


def test_e2e_no_global_state():
    import src.emergency.close as mod

    assert not hasattr(mod, "_emergency_tasks")
    assert not hasattr(mod, "_flush_controller")