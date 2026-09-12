import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.risk.whale_radar import WhaleRadar, WhaleRadarConfig

def _make_radar():
    cfg = WhaleRadarConfig()
    sqlite_writer = MagicMock()
    sqlite_writer.execute_wal = AsyncMock(return_value=None)
    lock = asyncio.Lock()
    numba_cvd = MagicMock()
    numba_cvd.warmup = MagicMock()
    radar = WhaleRadar(cfg, sqlite_writer, lock, numba_cvd)
    return radar, cfg

def test_config_defaults():
    cfg = WhaleRadarConfig()
    assert cfg.big_order_usd == 100_000.0
    assert cfg.oi_delta_usd_min == 50_000.0
    assert cfg.real_min_lifetime_ms == 3000
    assert cfg.real_min_fill_ratio == 0.30
    assert cfg.spoof_max_ratio == 0.10
    assert cfg.sweep_multiplier == 1.5
    assert cfg.band_fingerprint_mult == 5
    assert cfg.taker_buy_ratio_min == 0.6

def test_warmup():
    radar, _ = _make_radar()
    radar.warmup()
    radar._numba.warmup.assert_called()

@pytest.mark.asyncio
async def test_record_trade_big_order():
    radar, _ = _make_radar()
    await radar.record_trade("BTCUSDT", 50000.0, 0.1, 4000, 0.5, 100_000.0, 1234567890000)
    assert len(radar._trades["BTCUSDT"]) == 1

@pytest.mark.asyncio
async def test_record_trade_small_oi_filtered():
    radar, _ = _make_radar()
    await radar.record_trade("BTCUSDT", 50000.0, 0.1, 4000, 0.5, 10_000.0, 1234567890000)
    assert len(radar._trades["BTCUSDT"]) == 0

@pytest.mark.asyncio
async def test_record_trade_spoof_detection():
    radar, _ = _make_radar()
    await radar.record_trade("BTCUSDT", 50000.0, 0.1, 100, 0.05, 60_000.0, 1234567890000)
    assert radar._trades["BTCUSDT"][0]["is_spoof"] is True
    assert radar._trades["BTCUSDT"][0]["is_real"] is False

def test_get_trust_score():
    radar, _ = _make_radar()
    score = radar.get_trust_score("BTCUSDT", 50000.0, 0.1)
    assert 0.0 <= score <= 1.0

def test_band_fingerprint():
    radar, _ = _make_radar()
    key1 = radar._band_key(50000.0, 0.1)
    key2 = radar._band_key(50002.0, 0.1)
    # close prices should be similar band or nearby
    assert isinstance(key1, int)

def test_check_wash_true():
    radar, _ = _make_radar()
    # cvd up, oi down -> wash
    assert radar.check_wash(True, False, 0.8) is True

def test_check_wash_false():
    radar, _ = _make_radar()
    # cvd up, oi up, taker buy ratio high -> not wash
    assert radar.check_wash(True, True, 0.7) is False

@pytest.mark.asyncio
async def test_cleanup_old():
    radar, _ = _make_radar()
    import time

    old_ts = int((time.time() - 25 * 3600) * 1000)
    await radar.record_trade("BTCUSDT", 50000.0, 0.1, 4000, 0.5, 100_000.0, old_ts)
    removed = await radar.cleanup_old()
    assert removed >= 1

def test_no_global_state():
    assert not hasattr(WhaleRadar, "_trades")