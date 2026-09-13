"""
Chaos: FLIP detection on sign change.
Y-283 FLIP emergency_close, Y-295 lock disinda, Y-289 same sign assert.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.execution.order_manager import OrderManager, OrderManagerConfig


def _mk_om():
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
    return OrderManager(cfg, fill_lock, sqlite, sealed, rest), sqlite, fill_lock


@pytest.mark.asyncio
async def test_flip_long_to_short_emergency():
    om, sqlite, _ = _mk_om()
    om._filled_by_order["oid1"] = 1.0  # positive
    await om.on_fill_event("oid1", -1.0, 100.0, 123, "pos1")
    om._rest.emergency_close.assert_awaited()


@pytest.mark.asyncio
async def test_flip_short_to_long_emergency():
    om, sqlite, _ = _mk_om()
    om._filled_by_order["oid1"] = -0.5  # negative
    await om.on_fill_event("oid1", 0.5, 100.0, 123, "pos1")
    om._rest.emergency_close.assert_awaited()


@pytest.mark.asyncio
async def test_flip_outside_fill_lock():
    """Y-295: emergency_close called outside fill_lock."""
    om, sqlite, fill_lock = _mk_om()
    om._filled_by_order["oid1"] = 1.0

    lock_state = []

    async def fake_close(oid):
        lock_state.append(fill_lock.locked())

    om._rest.emergency_close = AsyncMock(side_effect=fake_close)
    await om.on_fill_event("oid1", -1.0, 100.0, 123, "pos1")

    assert lock_state == [False]


@pytest.mark.asyncio
async def test_flip_writes_close_position_db():
    om, sqlite, _ = _mk_om()
    om._filled_by_order["oid1"] = 1.0
    await om.on_fill_event("oid1", -1.0, 100.0, 123, "pos1")
    sqlite.close_position.assert_awaited()
    kwargs = sqlite.close_position.await_args.kwargs
    assert kwargs["close_reason"] == "FLIP"


@pytest.mark.asyncio
async def test_flip_no_position_update():
    om, sqlite, _ = _mk_om()
    om._filled_by_order["oid1"] = 1.0
    await om.on_fill_event("oid1", -1.0, 100.0, 123, "pos1")
    # FLIP short-circuits before position update
    sqlite.update_position_versioned.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_sign_no_flip():
    om, sqlite, _ = _mk_om()
    om._filled_by_order["oid1"] = 1.0
    await om.on_fill_event("oid1", 2.0, 101.0, 123, "pos1")
    om._rest.emergency_close.assert_not_awaited()
    assert om._filled_by_order["oid1"] == 2.0


@pytest.mark.asyncio
async def test_initial_fill_no_flip():
    """First fill of a new order cannot flip."""
    om, _, _ = _mk_om()
    await om.on_fill_event("oid_new", 1.0, 100.0, 123, "pos1")
    om._rest.emergency_close.assert_not_awaited()


def test_no_global_state():
    assert not hasattr(OrderManager, "_filled_by_order")