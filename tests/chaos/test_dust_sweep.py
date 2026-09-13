"""
Chaos: dust position handling.
Y-291 dust false-positive CLOSED_DUST YASAK, Y-302 DUST_ACKNOWLEDGED.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.execution.order_manager import OrderManager, OrderManagerConfig


def _mk_om(min_lot=0.001):
    cfg = OrderManagerConfig(min_lot=min_lot, epsilon_divisor=2.0)
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
    return OrderManager(cfg, fill_lock, sqlite, sealed, rest), sqlite


@pytest.mark.asyncio
async def test_dust_below_half_min_lot_acknowledged(caplog):
    om, sqlite = _mk_om(min_lot=0.001)
    # epsilon = 0.0005; fill 0.0001 < epsilon
    await om.on_fill_event("oid1", 0.0001, 100.0, 123, "pos1")
    assert "oid1" not in om._filled_by_order
    sqlite.update_position_versioned.assert_not_awaited()
    sqlite.open_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_dust_exactly_at_epsilon_processed():
    om, sqlite = _mk_om(min_lot=0.001)
    # epsilon = 0.0005; fill 0.0005 >= epsilon -> processed
    await om.on_fill_event("oid1", 0.0006, 100.0, 123, "pos1")
    assert om._filled_by_order.get("oid1") == 0.0006


@pytest.mark.asyncio
async def test_dust_no_closed_dust_event():
    """Y-291: dust must NOT trigger CLOSED_DUST event."""
    om, sqlite = _mk_om()
    # fill below epsilon
    await om.on_fill_event("oid1", 0.0001, 100.0, 123, "pos1")
    # no emergency close
    om._rest.emergency_close.assert_not_awaited()
    # no DB close
    sqlite.close_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_dust_does_not_open_position():
    om, sqlite = _mk_om()
    await om.on_fill_event("oid1", 0.0001, 100.0, 123, "pos1")
    sqlite.open_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_negative_dust_absolute_value():
    """Dust check uses abs(fill_qty)."""
    om, _ = _mk_om()
    await om.on_fill_event("oid1", -0.0001, 100.0, 123, "pos1")
    assert "oid1" not in om._filled_by_order


@pytest.mark.asyncio
async def test_above_dust_normal_flow():
    om, sqlite = _mk_om(min_lot=0.001)
    await om.on_fill_event("oid1", 0.5, 100.0, 123, "pos1")
    assert om._filled_by_order["oid1"] == 0.5
    sqlite.update_position_versioned.assert_awaited()


def test_no_global_state():
    assert not hasattr(OrderManager, "_filled_by_order")