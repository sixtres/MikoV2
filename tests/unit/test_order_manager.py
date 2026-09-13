# YAMA Y-258, Y-260, Y-283, Y-289, Y-291, Y-295, Y-297, Y-302, Y-315, Y-323, Y-339/350, Y-353, Y-358

import asyncio
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.execution.order_manager import OrderManager, OrderManagerConfig

def _make_deps():
    fill_lock = asyncio.Lock()
    sqlite_writer = MagicMock()
    sqlite_writer.fetch = AsyncMock(return_value=[])
    sqlite_writer.get_version = AsyncMock(return_value=1)
    sqlite_writer.update_position_versioned = AsyncMock(return_value=True)
    sqlite_writer.open_position = AsyncMock(return_value=None)
    sqlite_writer.close_position = AsyncMock(return_value=None)
    sealed_store = MagicMock()
    rest_gateway = MagicMock()
    rest_gateway.emergency_close = AsyncMock(return_value=True)
    return fill_lock, sqlite_writer, sealed_store, rest_gateway

def test_config_defaults():
    cfg = OrderManagerConfig()
    assert cfg.max_retry == 3
    assert cfg.leverage == 5
    assert cfg.min_lot == 0.001
    assert cfg.epsilon_divisor == 2.0

def test_leverage_adjusted_slippage_5x():
    cfg = OrderManagerConfig(leverage=5)
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    assert math.isclose(om.leverage_adjusted_slippage(), 0.02, abs_tol=1e-9)

def test_leverage_adjusted_slippage_20x():
    cfg = OrderManagerConfig(leverage=20)
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    assert math.isclose(om.leverage_adjusted_slippage(), 0.005, abs_tol=1e-9)

def test_leverage_adjusted_slippage_30x():
    cfg = OrderManagerConfig(leverage=30)
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    expected = min(0.03, 0.10 / 30)
    assert math.isclose(om.leverage_adjusted_slippage(), expected, abs_tol=1e-9)

def test_leverage_adjusted_slippage_3x_ceiling():
    cfg = OrderManagerConfig(leverage=3)
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    assert math.isclose(om.leverage_adjusted_slippage(), 0.03, abs_tol=1e-9)

def test_quantize_qty_round_down():
    cfg = OrderManagerConfig()
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    assert om.quantize_qty(1.9999, 3) == "1.999"

def test_quantize_qty_str_input():
    cfg = OrderManagerConfig()
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    result = om.quantize_qty(0.123456, 2)
    assert result == "0.12"

@pytest.mark.asyncio
async def test_on_startup_recovers_partial():
    cfg = OrderManagerConfig()
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    sqlite_writer.fetch = AsyncMock(return_value=[("order1", "1.5"), ("order2", "2.0")])
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    await om.on_startup()
    assert om._filled_by_order["order1"] == 1.5
    assert om._filled_by_order["order2"] == 2.0

@pytest.mark.asyncio
async def test_on_fill_event_ignores_zero():
    cfg = OrderManagerConfig()
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    await om.on_fill_event("oid1", 0.0, 100.0, 123, "pos1")
    assert "oid1" not in om._filled_by_order

@pytest.mark.asyncio
async def test_on_fill_event_first_fill():
    cfg = OrderManagerConfig()
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    await om.on_fill_event("oid1", 1.0, 100.0, 123, "pos1")
    assert om._filled_by_order["oid1"] == 1.0

@pytest.mark.asyncio
async def test_on_fill_event_flip_calls_emergency_outside_lock():
    cfg = OrderManagerConfig()
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    om._filled_by_order["oid1"] = 1.0

    lock_acquired_during_close = None

    async def fake_close(order_id):
        nonlocal lock_acquired_during_close
        lock_acquired_during_close = fill_lock.locked()

    rest_gateway.emergency_close = AsyncMock(side_effect=fake_close)

    await om.on_fill_event("oid1", -1.0, 100.0, 123, "pos1")
    assert lock_acquired_during_close is False
    rest_gateway.emergency_close.assert_awaited()

@pytest.mark.asyncio
async def test_on_fill_event_dust_acknowledged():
    cfg = OrderManagerConfig(min_lot=0.001, epsilon_divisor=2.0)
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    with patch("src.execution.order_manager.logger") as mock_logger:
        await om.on_fill_event("oid1", 0.0001, 100.0, 123, "pos1")
        mock_logger.warning.assert_called()
        assert "DUST_ACKNOWLEDGED" in str(mock_logger.warning.call_args)

@pytest.mark.asyncio
async def test_on_fill_event_retry_version_conflict():
    cfg = OrderManagerConfig(max_retry=3)
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    sqlite_writer.update_position_versioned = AsyncMock(
        side_effect=[Exception("conflict"), True]
    )
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    await om.on_fill_event("oid1", 1.0, 100.0, 123, "pos1")
    assert om._filled_by_order["oid1"] == 1.0
    assert sqlite_writer.update_position_versioned.await_count == 2

@pytest.mark.asyncio
async def test_on_fill_event_advance_after_commit():
    cfg = OrderManagerConfig()
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    await om.on_fill_event("oid1", 1.0, 100.0, 123, "pos1")
    assert sqlite_writer.update_position_versioned.await_count == 1
    assert om._filled_by_order["oid1"] == 1.0

@pytest.mark.asyncio
async def test_on_fill_event_max_retry_exhausted():
    cfg = OrderManagerConfig(max_retry=2)
    fill_lock, sqlite_writer, sealed_store, rest_gateway = _make_deps()
    sqlite_writer.update_position_versioned = AsyncMock(
        side_effect=Exception("always fail")
    )
    om = OrderManager(cfg, fill_lock, sqlite_writer, sealed_store, rest_gateway)
    with patch("src.execution.order_manager.logger") as mock_logger:
        await om.on_fill_event("oid1", 1.0, 100.0, 123, "pos1")
        # should log exhausted
        assert any(
            "max retry exhausted" in str(call).lower()
            for call in mock_logger.warning.call_args_list
        )
    assert "oid1" not in om._filled_by_order

def test_no_global_state():
    assert not hasattr(OrderManager, "_filled_by_order")

@pytest.mark.asyncio
async def test_on_fill_event_opens_position_in_db():
    """First fill event creates position row."""
    cfg = OrderManagerConfig()
    fill_lock = asyncio.Lock()
    sqlite = MagicMock()
    sqlite.fetch = AsyncMock(return_value=[])
    sqlite.get_version = AsyncMock(return_value=0)
    sqlite.update_position_versioned = AsyncMock(return_value=True)
    sqlite.open_position = AsyncMock(return_value=None)
    sqlite.close_position = AsyncMock(return_value=None)
    sealed = MagicMock()
    rest = MagicMock()
    rest.emergency_close = AsyncMock(return_value=True)

    om = OrderManager(cfg, fill_lock, sqlite, sealed, rest)
    om.register_position("pos1", "BTC_USDT", "LONG", "IN_TOP5", 2)

    await om.on_fill_event("oid1", 1.0, 100.0, 123, "pos1")

    sqlite.open_position.assert_awaited_once()
    call_kwargs = sqlite.open_position.await_args[0][0]
    assert call_kwargs["position_id"] == "pos1"
    assert call_kwargs["symbol"] == "BTC_USDT"
    assert call_kwargs["side"] == "LONG"
    assert call_kwargs["universe_status"] == "IN_TOP5"
    assert call_kwargs["whale_trust_score"] == 2


@pytest.mark.asyncio
async def test_on_fill_event_opens_position_once():
    """Second fill on same position does not re-open row."""
    cfg = OrderManagerConfig()
    fill_lock = asyncio.Lock()
    sqlite = MagicMock()
    sqlite.fetch = AsyncMock(return_value=[])
    sqlite.get_version = AsyncMock(return_value=0)
    sqlite.update_position_versioned = AsyncMock(return_value=True)
    sqlite.open_position = AsyncMock(return_value=None)
    sqlite.close_position = AsyncMock(return_value=None)
    sealed = MagicMock()
    rest = MagicMock()
    rest.emergency_close = AsyncMock(return_value=True)

    om = OrderManager(cfg, fill_lock, sqlite, sealed, rest)
    om.register_position("pos1", "BTC_USDT", "LONG")

    await om.on_fill_event("oid1", 0.5, 100.0, 100, "pos1")
    await om.on_fill_event("oid2", 0.5, 101.0, 200, "pos1")

    assert sqlite.open_position.await_count == 1


@pytest.mark.asyncio
async def test_on_fill_event_flip_closes_position_in_db():
    cfg = OrderManagerConfig()
    fill_lock = asyncio.Lock()
    sqlite = MagicMock()
    sqlite.fetch = AsyncMock(return_value=[])
    sqlite.get_version = AsyncMock(return_value=0)
    sqlite.update_position_versioned = AsyncMock(return_value=True)
    sqlite.open_position = AsyncMock(return_value=None)
    sqlite.close_position = AsyncMock(return_value=None)
    sealed = MagicMock()
    rest = MagicMock()
    rest.emergency_close = AsyncMock(return_value=True)

    om = OrderManager(cfg, fill_lock, sqlite, sealed, rest)
    om.register_position("pos1", "BTC_USDT", "LONG")
    om._filled_by_order["oid1"] = 1.0

    await om.on_fill_event("oid1", -1.0, 100.0, 123, "pos1")

    sqlite.close_position.assert_awaited()
    kwargs = sqlite.close_position.await_args.kwargs
    assert kwargs["position_id"] == "pos1"
    assert kwargs["close_reason"] == "FLIP"


@pytest.mark.asyncio
async def test_register_position_stores_metadata():
    cfg = OrderManagerConfig()
    fill_lock = asyncio.Lock()
    sqlite = MagicMock()
    om = OrderManager(cfg, fill_lock, sqlite, MagicMock(), MagicMock())
    om.register_position("pos1", "BTC_USDT", "SHORT", "IN_TOP10", 3)
    assert om._position_symbol["pos1"] == "BTC_USDT"
    assert om._position_side["pos1"] == "SHORT"
    assert om._position_universe["pos1"] == "IN_TOP10"
    assert om._position_whale_trust["pos1"] == 3    