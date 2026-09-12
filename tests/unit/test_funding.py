import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.risk.funding import FundingMonitor, FundingMonitorConfig

def _make_monitor():
    cfg = FundingMonitorConfig()
    sqlite_writer = MagicMock()
    sqlite_writer.execute_wal = AsyncMock(return_value=None)
    lock = asyncio.Lock()
    mon = FundingMonitor(cfg, sqlite_writer, lock)
    return mon, cfg

def test_config_defaults():
    cfg = FundingMonitorConfig()
    assert cfg.environment == "TEST"
    assert cfg.funding_times_utc == (0, 8, 16)
    assert cfg.funding_rate_threshold == 0.001
    assert cfg.daily_reset_hour_utc == 0
    assert cfg.weekly_reset_day == "MONDAY"

def test_max_daily_loss_and_budget():
    mon, _ = _make_monitor()
    assert mon.max_daily_loss == -0.04
    assert mon.risk_budget == 0.04

@pytest.mark.asyncio
async def test_check_funding_time_true():
    mon, _ = _make_monitor()
    assert await mon.check_funding_time(0) is True
    assert await mon.check_funding_time(8) is True
    assert await mon.check_funding_time(16) is True

@pytest.mark.asyncio
async def test_check_funding_time_false():
    mon, _ = _make_monitor()
    assert await mon.check_funding_time(1) is False
    assert await mon.check_funding_time(12) is False

@pytest.mark.asyncio
async def test_record_and_get_funding_rate():
    mon, _ = _make_monitor()
    await mon.record_funding_rate("BTCUSDT", 0.0012, 1234567890000)
    rate = await mon.get_funding_rate("BTCUSDT")
    assert rate == 0.0012

@pytest.mark.asyncio
async def test_get_funding_rate_none():
    mon, _ = _make_monitor()
    rate = await mon.get_funding_rate("NONEXIST")
    assert rate is None

@pytest.mark.asyncio
async def test_check_daily_loss_ok():
    mon, _ = _make_monitor()
    mon._daily_pnl = -0.01
    ok, pnl = await mon.check_daily_loss()
    assert ok is True

@pytest.mark.asyncio
async def test_check_daily_loss_exceeded():
    mon, _ = _make_monitor()
    mon._daily_pnl = -0.05
    ok, pnl = await mon.check_daily_loss()
    assert ok is False

@pytest.mark.asyncio
async def test_update_and_reset_daily():
    mon, _ = _make_monitor()
    await mon.update_daily_pnl(-0.01)
    assert mon._daily_pnl == -0.01
    await mon.update_daily_pnl(-0.02)
    assert mon._daily_pnl == -0.03
    await mon.reset_daily()
    assert mon._daily_pnl == 0.0

def test_no_global_state():
    assert not hasattr(FundingMonitor, "_daily_pnl")