import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.emergency.close import EmergencyCloser, EmergencyCloserConfig


def _make_closer(rest_result=None, rest_exc=None):
    cfg = EmergencyCloserConfig(reduce_only=True, max_retry=1, leverage=5, min_lot=0.001)
    rest = MagicMock()
    if rest_exc is not None:
        rest.post_market_order = AsyncMock(side_effect=rest_exc)
    else:
        rest.post_market_order = AsyncMock(return_value=rest_result)
    rest._direct_market_post = AsyncMock(return_value={"status": "forced"})
    sqlite = MagicMock()
    sqlite.execute_wal = AsyncMock(return_value=None)
    sealed = MagicMock()
    flush = MagicMock()
    flush.suspend = MagicMock()
    flush.resume = MagicMock()
    tasks = {}
    return EmergencyCloser(cfg, rest, sqlite, sealed, flush, tasks), tasks, rest, flush


def test_config_defaults():
    cfg = EmergencyCloserConfig()
    assert cfg.reduce_only is True
    assert cfg.max_retry == 1
    assert cfg.leverage == 5
    assert cfg.min_lot == 0.001


def test_leverage_adjusted_slippage_5x():
    closer, _, _, _ = _make_closer()
    assert abs(closer.leverage_adjusted_slippage() - 0.02) < 1e-9


def test_leverage_adjusted_slippage_20x():
    cfg = EmergencyCloserConfig(leverage=20)
    closer = EmergencyCloser(cfg, MagicMock(), MagicMock(), MagicMock(), MagicMock(), {})
    assert abs(closer.leverage_adjusted_slippage() - 0.005) < 1e-9


def test_quantize_qty_round_down():
    closer, _, _, _ = _make_closer()
    assert closer.quantize_qty(1.9999, 3) == "1.999"


@pytest.mark.asyncio
async def test_close_success():
    closer, tasks, rest, flush = _make_closer(rest_result={"status": "ok", "slippage": 0.0})
    result = await closer.emergency_close_with_retry("BTCUSDT")
    assert result == "CLOSED"
    assert flush.suspend.called
    assert flush.resume.called


@pytest.mark.asyncio
async def test_close_single_flight_same_symbol():
    closer, tasks, rest, _ = _make_closer(rest_result={"status": "ok", "slippage": 0.0})
    task1 = asyncio.create_task(closer.emergency_close_with_retry("BTCUSDT"))
    task2 = asyncio.create_task(closer.emergency_close_with_retry("BTCUSDT"))
    r1, r2 = await asyncio.gather(task1, task2)
    assert r1 == "CLOSED"
    assert r2 == "CLOSED"
    assert rest.post_market_order.await_count == 1


@pytest.mark.asyncio
async def test_task_pop_after_done():
    closer, tasks, _, _ = _make_closer(rest_result={"status": "ok", "slippage": 0.0})
    await closer.emergency_close_with_retry("BTCUSDT")
    await asyncio.sleep(0.01)
    assert "BTCUSDT" not in tasks


@pytest.mark.asyncio
async def test_pacer_full_fallback_direct():
    closer, _, rest, _ = _make_closer()
    rest.post_market_order = AsyncMock(side_effect=RuntimeError("pacer full"))
    result = await closer.emergency_close_with_retry("BTCUSDT")
    assert result == "FORCE_LIQUIDATED_BY_SYSTEM"
    rest._direct_market_post.assert_awaited()


@pytest.mark.asyncio
async def test_direct_market_post_none_failure():
    closer, _, rest, _ = _make_closer()
    rest.post_market_order = AsyncMock(side_effect=RuntimeError("pacer full"))
    rest._direct_market_post = AsyncMock(return_value=None)
    result = await closer.emergency_close_with_retry("BTCUSDT")
    assert result == "EMERGENCY_FAILED_POSITION_OPEN"


@pytest.mark.asyncio
async def test_slippage_retry_force_liq():
    closer, _, _, _ = _make_closer()
    closer._rest.post_market_order = AsyncMock(
        return_value={"status": "ok", "slippage": 0.5}
    )
    result = await closer.emergency_close_with_retry("BTCUSDT")
    assert result == "FORCE_LIQUIDATED_BY_SYSTEM"


@pytest.mark.asyncio
async def test_flush_suspend_resume_called():
    closer, _, _, flush = _make_closer(rest_result={"status": "ok", "slippage": 0.0})
    await closer.emergency_close_with_retry("BTCUSDT")
    flush.suspend.assert_called_once()
    flush.resume.assert_called_once()


@pytest.mark.asyncio
async def test_persist_called_first():
    closer, _, _, _ = _make_closer(rest_result={"status": "ok", "slippage": 0.0})
    await closer.emergency_close_with_retry("BTCUSDT")
    closer._sqlite.execute_wal.assert_awaited()


def test_no_global_state():
    assert not hasattr(EmergencyCloser, "_tasks")