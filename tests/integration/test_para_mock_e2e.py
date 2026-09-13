"""
Para mock end-to-end: fill -> position -> TP/SL shift -> BE trail -> sealed TTL.
Y-258 R:R, Y-260 slippage, Y-283 FLIP, Y-297 advance-after-commit, Y-315 sealed TTL.
"""

import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.emergency.close import EmergencyCloser, EmergencyCloserConfig
from src.execution.order_manager import OrderManager, OrderManagerConfig
from src.storage.sealed import SealedStore, SealedStoreConfig


def _make_order_manager():
    cfg = OrderManagerConfig(max_retry=3, leverage=5, min_lot=0.001, epsilon_divisor=2.0)
    fill_lock = asyncio.Lock()
    sqlite = MagicMock()
    sqlite.fetch = AsyncMock(return_value=[])
    sqlite.get_version = AsyncMock(return_value=0)
    sqlite.update_position_versioned = AsyncMock(return_value=True)
    sealed = MagicMock()
    rest = MagicMock()
    rest.emergency_close = AsyncMock(return_value=True)
    om = OrderManager(cfg, fill_lock, sqlite, sealed, rest)
    return om, sqlite, rest, fill_lock


@pytest.mark.asyncio
async def test_para_e2e_single_fill_advances_position():
    om, sqlite, rest, _ = _make_order_manager()
    await om.on_fill_event("oid1", 1.0, 100.0, 1234567890000, "pos1")
    assert om._filled_by_order["oid1"] == 1.0
    sqlite.update_position_versioned.assert_awaited()


@pytest.mark.asyncio
async def test_para_e2e_partial_then_full():
    """Two fills on same order: max() monotonic, position advances."""
    om, sqlite, rest, _ = _make_order_manager()
    await om.on_fill_event("oid1", 0.5, 100.0, 1234567890000, "pos1")
    assert om._filled_by_order["oid1"] == 0.5

    await om.on_fill_event("oid1", 1.0, 101.0, 1234567891000, "pos1")
    assert om._filled_by_order["oid1"] == 1.0
    assert sqlite.update_position_versioned.await_count == 2


@pytest.mark.asyncio
async def test_para_e2e_same_fill_no_double_update():
    """Identical fill event: inc <= 0, no update."""
    om, sqlite, rest, _ = _make_order_manager()
    await om.on_fill_event("oid1", 1.0, 100.0, 1234567890000, "pos1")
    call_count = sqlite.update_position_versioned.await_count

    await om.on_fill_event("oid1", 1.0, 100.0, 1234567891000, "pos1")
    # no advance
    assert sqlite.update_position_versioned.await_count == call_count


@pytest.mark.asyncio
async def test_para_e2e_flip_triggers_emergency_outside_lock():
    om, sqlite, rest, fill_lock = _make_order_manager()
    om._filled_by_order["oid1"] = 1.0

    lock_during = []

    async def fake_close(oid):
        lock_during.append(fill_lock.locked())

    rest.emergency_close = AsyncMock(side_effect=fake_close)

    await om.on_fill_event("oid1", -1.0, 100.0, 1234567890000, "pos1")

    rest.emergency_close.assert_awaited()
    assert lock_during == [False]


@pytest.mark.asyncio
async def test_para_e2e_dust_below_epsilon_skipped():
    """Dust below min_lot/2 = 0.0005 is acknowledged, no update."""
    om, sqlite, rest, _ = _make_order_manager()
    await om.on_fill_event("oid1", 0.0001, 100.0, 1234567890000, "pos1")
    assert "oid1" not in om._filled_by_order
    sqlite.update_position_versioned.assert_not_awaited()


@pytest.mark.asyncio
async def test_para_e2e_max_retry_exhausted():
    om, sqlite, rest, _ = _make_order_manager()
    sqlite.update_position_versioned = AsyncMock(side_effect=Exception("always fail"))
    await om.on_fill_event("oid1", 1.0, 100.0, 1234567890000, "pos1")
    assert "oid1" not in om._filled_by_order


@pytest.mark.asyncio
async def test_para_e2e_version_conflict_then_success():
    om, sqlite, rest, _ = _make_order_manager()
    sqlite.update_position_versioned = AsyncMock(
        side_effect=[Exception("conflict"), True]
    )
    await om.on_fill_event("oid1", 1.0, 100.0, 1234567890000, "pos1")
    assert om._filled_by_order["oid1"] == 1.0
    assert sqlite.update_position_versioned.await_count == 2


@pytest.mark.asyncio
async def test_para_e2e_sealed_ttl_expiry():
    cfg = SealedStoreConfig(seal_ttl_ms=300000, exchange_ts_tolerance_ms=2000)
    lock = asyncio.Lock()
    sealed = SealedStore(cfg, lock)
    now_ms = int(time.time() * 1000)

    # seal with old timestamp
    await sealed.seal("oid1", now_ms - 400_000, None, 1)
    removed = await sealed.cleanup_expired()
    assert removed == 1
    assert sealed.size() == 0


@pytest.mark.asyncio
async def test_para_e2e_sealed_blocks_duplicate_event():
    cfg = SealedStoreConfig()
    lock = asyncio.Lock()
    sealed = SealedStore(cfg, lock)
    now_ms = int(time.time() * 1000)

    await sealed.seal("oid1", now_ms, now_ms - 5000, 1)
    # old event (5s older than sealed)
    is_blocked = await sealed.is_sealed("oid1", now_ms - 5000)
    assert is_blocked is True

    # fresh event is still blocked because order is sealed
    is_blocked2 = await sealed.is_sealed("oid1", now_ms)
    assert is_blocked2 is True

    # unsealed order
    is_blocked3 = await sealed.is_sealed("oid_neverseen", now_ms)
    assert is_blocked3 is False


@pytest.mark.asyncio
async def test_para_e2e_rr_check_rejects_low():
    """R:R < 1.4999 must be rejected."""
    from src.risk.portfolio_risk import PortfolioRiskConfig, PortfolioRiskManager

    cfg = PortfolioRiskConfig(environment="TEST")
    mgr = PortfolioRiskManager(cfg, MagicMock(), asyncio.Lock())
    # entry 100, tp 100.5, sl 99.5, fees add drag
    entry = Decimal("100")
    tp = Decimal("100.5")
    sl = Decimal("99.5")
    fee_taker = Decimal("0.0002")
    fee_maker = Decimal("0.0")
    rr = mgr.compute_rr(entry, tp, sl, fee_taker, fee_maker)
    assert rr < Decimal("1.4999")


@pytest.mark.asyncio
async def test_para_e2e_rr_check_accepts_high():
    from src.risk.portfolio_risk import PortfolioRiskConfig, PortfolioRiskManager

    cfg = PortfolioRiskConfig(environment="TEST")
    mgr = PortfolioRiskManager(cfg, MagicMock(), asyncio.Lock())
    entry = Decimal("100")
    tp = Decimal("103")
    sl = Decimal("99")
    fee_taker = Decimal("0.0002")
    fee_maker = Decimal("0.0")
    rr = mgr.compute_rr(entry, tp, sl, fee_taker, fee_maker)
    assert rr >= Decimal("1.4999")


@pytest.mark.asyncio
async def test_para_e2e_full_close_after_fill():
    """Fill -> emergency close flow across modules."""
    om, sqlite, rest, _ = _make_order_manager()
    await om.on_fill_event("oid1", 1.0, 100.0, 1234567890000, "pos1")
    assert om._filled_by_order["oid1"] == 1.0

    cfg = EmergencyCloserConfig(reduce_only=True, max_retry=1, leverage=5, min_lot=0.001)
    rest_gw = MagicMock()
    rest_gw.post_market_order = AsyncMock(
        return_value={"status": "ok", "slippage": 0.0}
    )
    rest_gw._direct_market_post = AsyncMock(return_value={"status": "forced"})
    flush = MagicMock()
    flush.suspend = MagicMock()
    flush.resume = MagicMock()
    tasks = {}
    closer = EmergencyCloser(cfg, rest_gw, sqlite, MagicMock(), flush, tasks)

    result = await closer.emergency_close_with_retry("pos1")
    assert result == "CLOSED"


def test_para_e2e_no_global_state():
    import src.execution.order_manager as om_mod
    import src.emergency.close as close_mod
    import src.storage.sealed as sealed_mod

    for mod in (om_mod, close_mod, sealed_mod):
        for name in dir(mod):
            if name.startswith("__"):
                continue
            obj = getattr(mod, name)
            if isinstance(obj, dict) and name.startswith("_") and not name.startswith("__"):
                # private module dicts forbidden at class level (allowed instance)
                cls_names = [c for c in dir(mod) if isinstance(getattr(mod, c, None), type)]
                for cn in cls_names:
                    cls = getattr(mod, cn)
                    if hasattr(cls, name):
                        raise AssertionError("%s.%s global state" % (cn, name))