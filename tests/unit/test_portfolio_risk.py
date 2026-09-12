from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.risk.portfolio_risk import PortfolioRiskConfig, PortfolioRiskManager

def _make_manager(env="TEST"):
    cfg = PortfolioRiskConfig(environment=env)
    sqlite_writer = MagicMock()
    sqlite_writer.fetch = AsyncMock(return_value=[[0]])
    sqlite_writer.execute_wal = AsyncMock(return_value=None)
    lock = MagicMock()
    # use asyncio.Lock real for async with
    import asyncio

    lock = asyncio.Lock()
    mgr = PortfolioRiskManager(cfg, sqlite_writer, lock)
    return mgr, cfg

def test_config_defaults():
    cfg = PortfolioRiskConfig()
    assert cfg.environment == "TEST"
    assert cfg.position_mode == "ONE_WAY"
    assert cfg.target_leverage == 5
    assert cfg.max_sl_distance == 0.025
    assert cfg.correlation_threshold == 0.85

def test_risk_per_trade_test_prod():
    mgr_test, _ = _make_manager("TEST")
    assert mgr_test.risk_per_trade == 0.008
    mgr_prod, _ = _make_manager("PROD")
    assert mgr_prod.risk_per_trade == 0.006

def test_max_positions():
    mgr_test, _ = _make_manager("TEST")
    assert mgr_test.max_positions == 3
    mgr_prod, _ = _make_manager("PROD")
    assert mgr_prod.max_positions == 2

def test_max_daily_loss():
    mgr_test, _ = _make_manager("TEST")
    assert mgr_test.max_daily_loss == -0.04
    mgr_prod, _ = _make_manager("PROD")
    assert mgr_prod.max_daily_loss == -0.02

def test_compute_rr_long():
    mgr, _ = _make_manager()
    entry = Decimal("100")
    tp = Decimal("102")
    sl = Decimal("99")
    fee_taker = Decimal("0.0004")
    fee_maker = Decimal("0.0002")
    rr = mgr.compute_rr(entry, tp, sl, fee_taker, fee_maker)
    # gross 2 /1 =2, net slightly less but >1.4
    assert rr > Decimal("1.4")

def test_compute_rr_short():
    mgr, _ = _make_manager()
    entry = Decimal("100")
    tp = Decimal("98")
    sl = Decimal("101")
    fee_taker = Decimal("0.0004")
    fee_maker = Decimal("0.0002")
    rr = mgr.compute_rr(entry, tp, sl, fee_taker, fee_maker)
    assert rr > Decimal("1.4")

def test_compute_rr_net_fee_14999():
    mgr, _ = _make_manager()
    # 1.4999 target: entry 100 tp 101.5 sl 99 with fees
    entry = Decimal("100")
    tp = Decimal("101.5")
    sl = Decimal("99")
    fee_taker = Decimal("0.0004")
    fee_maker = Decimal("0.0002")
    rr = mgr.compute_rr(entry, tp, sl, fee_taker, fee_maker)
    # should be around 1.4999 net fee
    assert Decimal("1.3") <= rr <= Decimal("1.6")

@pytest.mark.asyncio
async def test_check_new_position_ok():
    mgr, _ = _make_manager()
    ok, msg = await mgr.check_new_position("BTCUSDT", "LONG", Decimal("0.01"), Decimal("50000"))
    assert ok is True
    assert msg == "OK"

@pytest.mark.asyncio
async def test_check_new_position_max_exceeded():
    import asyncio

    cfg = PortfolioRiskConfig(environment="TEST")
    sqlite_writer = MagicMock()
    sqlite_writer.fetch = AsyncMock(return_value=[[3]])
    mgr = PortfolioRiskManager(cfg, sqlite_writer, asyncio.Lock())
    ok, msg = await mgr.check_new_position("BTCUSDT", "LONG", Decimal("0.01"), Decimal("50000"))
    assert ok is False
    assert "MAX_POSITIONS" in msg

@pytest.mark.asyncio
async def test_check_second_entry_true():
    mgr, _ = _make_manager()
    ok = await mgr.check_second_entry("pos1", True)
    assert ok is True

@pytest.mark.asyncio
async def test_check_second_entry_false():
    mgr, _ = _make_manager()
    ok = await mgr.check_second_entry("pos1", False)
    assert ok is False

@pytest.mark.asyncio
async def test_check_daily_loss_ok():
    mgr, _ = _make_manager()
    mgr._daily_pnl = Decimal("-0.01")
    ok, pnl = await mgr.check_daily_loss()
    assert ok is True

@pytest.mark.asyncio
async def test_check_daily_loss_exceeded():
    mgr, _ = _make_manager("TEST")
    mgr._daily_pnl = Decimal("-0.05")
    ok, pnl = await mgr.check_daily_loss()
    assert ok is False

def test_no_global_state():
    assert not hasattr(PortfolioRiskManager, "_daily_pnl")