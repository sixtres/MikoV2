# tests/unit/test_b3_3_paper_manager.py
# B3.3 — Paper position manager + paper_math unit tests.
#
# Kapsam:
#   - paper_math saf fonksiyonlari (parite, yon, qty, R, fee, ATR)
#   - PaperPositionManager: setup_db, on_entry, TP exit, SL exit,
#     global limit, per-symbol limit, stale price, atr_not_ready,
#     startup rehydration, determinism, entry_bucket_sec skip.
#
# In-memory SQLite. Gercek ag yok.

from __future__ import annotations

import sqlite3
from collections import deque

import pytest

from src.execution.paper_position_manager import (
    OhlcvSample,
    PaperPositionConfig,
    PaperPositionManager,
    _Candle5s,
)
from src.trading import paper_math as pm


# ---------------------------------------------------------- helpers


def _cfg(**overrides) -> PaperPositionConfig:
    base = dict(
        initial_equity=10_000.0,
        risk_pct=0.006,
        atr_period=14,
        sl_atr_multiplier=0.5,
        tp_r_multiple=2.0,
        max_sl_distance_pct=0.025,
        min_sl_distance_pct=0.002,
        entry_slippage_bps=2.0,
        fee_taker=0.0002,
        fee_maker=0.0,
        include_funding=False,
        max_positions_per_symbol=1,
        max_positions_global=2,
        stale_price_ms=5_000,
        config_profile_tag="TEST_PAPER",
    )
    base.update(overrides)
    return PaperPositionConfig(**base)


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    return c


def _manager(cfg: PaperPositionConfig | None = None) -> PaperPositionManager:
    cfg = cfg or _cfg()
    m = PaperPositionManager(
        cfg,
        _conn(),
        mono_ms_fn=lambda: 1_000_000,
        wall_ms_fn=lambda: 2_000_000,
    )
    m.setup_db()
    return m


def _warm_ohlcv_1s(
    m: PaperPositionManager, symbol: str, base: float, n: int = 100
) -> None:
    """ATR warmup + 5s candle assembly icin 1s OHLCV besle.
    n=100 -> 20 adet 5s mum."""
    for i in range(n):
        sec = i + 1
        m.on_ohlcv(OhlcvSample(
            symbol=symbol, sec=sec, ts_ms=sec * 1000,
            open=base, high=base + 0.5, low=base - 0.5, close=base,
        ))


# ============================================================ paper_math


def test_apply_entry_slippage_long() -> None:
    assert pm.apply_entry_slippage(100.0, pm.LONG, 2.0) == pytest.approx(100.02)


def test_apply_entry_slippage_short() -> None:
    assert pm.apply_entry_slippage(100.0, pm.SHORT, 2.0) == pytest.approx(99.98)


def test_apply_entry_slippage_non_positive() -> None:
    assert pm.apply_entry_slippage(0.0, pm.LONG, 2.0) == 0.0
    assert pm.apply_entry_slippage(-5.0, pm.LONG, 2.0) == 0.0


def test_compute_sl_distance_clamps_to_cap() -> None:
    # raw = 0.5*10 = 5; cap = 0.025*100 = 2.5; floor = 0.002*100 = 0.2
    d = pm.compute_sl_distance(
        10.0, 100.0,
        sl_atr_multiplier=0.5,
        max_sl_distance_pct=0.025,
        min_sl_distance_pct=0.002,
    )
    assert d == pytest.approx(2.5)


def test_compute_sl_distance_clamps_to_floor() -> None:
    # raw = 0.5*0.05 = 0.025; floor = 0.002*100 = 0.2
    d = pm.compute_sl_distance(
        0.05, 100.0,
        sl_atr_multiplier=0.5,
        max_sl_distance_pct=0.025,
        min_sl_distance_pct=0.002,
    )
    assert d == pytest.approx(0.2)


def test_compute_sl_price_long_short() -> None:
    assert pm.compute_sl_price(100.0, 2.0, pm.LONG) == 98.0
    assert pm.compute_sl_price(100.0, 2.0, pm.SHORT) == 102.0


def test_compute_tp_price_long_short() -> None:
    assert pm.compute_tp_price(100.0, 2.0, 2.0, pm.LONG) == 104.0
    assert pm.compute_tp_price(100.0, 2.0, 2.0, pm.SHORT) == 96.0


def test_compute_qty_zero_sl_distance() -> None:
    assert pm.compute_qty(10_000.0, 0.006, 0.0) == 0.0


def test_compute_qty_basic() -> None:
    # 10000 * 0.006 / 2 = 30
    assert pm.compute_qty(10_000.0, 0.006, 2.0) == pytest.approx(30.0)


def test_compute_r_multiple_long() -> None:
    assert pm.compute_r_multiple(100.0, 104.0, 98.0, pm.LONG) == pytest.approx(2.0)


def test_compute_r_multiple_short() -> None:
    assert pm.compute_r_multiple(100.0, 96.0, 102.0, pm.SHORT) == pytest.approx(2.0)


def test_compute_pnl_gross_long_short() -> None:
    assert pm.compute_pnl_gross(100.0, 104.0, 10.0, pm.LONG) == pytest.approx(40.0)
    assert pm.compute_pnl_gross(100.0, 96.0, 10.0, pm.SHORT) == pytest.approx(40.0)


def test_compute_exit_fee_tp_uses_maker() -> None:
    fee = pm.compute_exit_fee(104.0, 10.0, 0.0002, 0.0, pm.TP)
    assert fee == 0.0


def test_compute_exit_fee_sl_uses_taker() -> None:
    fee = pm.compute_exit_fee(98.0, 10.0, 0.0002, 0.0, pm.SL)
    assert fee == pytest.approx(98.0 * 10.0 * 0.0002)


def test_compute_atr_not_ready() -> None:
    candles = [_Candle5s(0, 0, 1.0, 1.0, 1.0, 1.0)]
    assert pm.compute_atr(candles, 14) is None


def test_compute_atr_basic() -> None:
    candles = [
        _Candle5s(i * 5, i * 5000, 100.0, 101.0, 99.0, 100.0)
        for i in range(15)
    ]
    atr = pm.compute_atr(candles, 14)
    assert atr is not None
    assert atr > 0.0


def test_funding_delta_long_short() -> None:
    assert pm.compute_funding_delta(0.001, 1000.0, pm.LONG) == pytest.approx(1.0)
    assert pm.compute_funding_delta(0.001, 1000.0, pm.SHORT) == pytest.approx(-1.0)


# ============================================================ manager: setup


def test_setup_db_creates_tables() -> None:
    m = _manager()
    cur = m._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name IN ('paper_positions','paper_events')"
    )
    names = {row[0] for row in cur}
    assert "paper_positions" in names
    assert "paper_events" in names


# ============================================================ manager: entry


@pytest.mark.asyncio
async def test_entry_rejected_when_atr_not_ready() -> None:
    m = _manager()
    # hic mum yok -> ATR not ready
    m.on_ws_tick("BTC_USDT", 100.0, mono_ms=999_000)
    ok = await m.on_entry(
        "BTC_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    assert ok is False
    assert m.last_rejection_reason == "atr_not_ready"


@pytest.mark.asyncio
async def test_entry_rejected_when_stale_price() -> None:
    m = _manager()
    _warm_ohlcv_1s(m, "BTC_USDT", 100.0, 100)
    m.on_ws_tick("BTC_USDT", 100.0, mono_ms=100_000)
    # simdi 1_000_000 -> 900s gecmis > 5000ms stale
    ok = await m.on_entry(
        "BTC_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    assert ok is False
    assert m.last_rejection_reason == "stale_price"


@pytest.mark.asyncio
async def test_entry_opens_position() -> None:
    m = _manager()
    _warm_ohlcv_1s(m, "BTC_USDT", 100.0, 100)
    m.on_ws_tick("BTC_USDT", 100.0, mono_ms=999_000)
    ok = await m.on_entry(
        "BTC_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    assert ok is True
    assert "BTC_USDT" in m.open_positions
    pos = m.open_positions["BTC_USDT"]
    # 2 bps LONG -> entry_fill 100.02
    assert pos.entry_price == pytest.approx(100.02)
    assert pos.direction == pm.LONG
    # qty = equity(10000) * 0.006 / sl_distance
    assert pos.qty > 0.0


@pytest.mark.asyncio
async def test_entry_rejects_second_per_symbol() -> None:
    m = _manager()
    _warm_ohlcv_1s(m, "BTC_USDT", 100.0, 100)
    m.on_ws_tick("BTC_USDT", 100.0, mono_ms=999_000)
    ok1 = await m.on_entry(
        "BTC_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    assert ok1 is True
    ok2 = await m.on_entry(
        "BTC_USDT", pm.LONG, signal_ts_ms=1_001_000,
        last_price=100.0, mono_ms=1_001_000,
    )
    assert ok2 is False
    assert m.last_rejection_reason == "per_symbol_max_position"


@pytest.mark.asyncio
async def test_entry_rejects_when_global_limit_full() -> None:
    cfg = _cfg(max_positions_global=1, max_positions_per_symbol=1)
    m = _manager(cfg)
    _warm_ohlcv_1s(m, "AAA_USDT", 100.0, 100)
    _warm_ohlcv_1s(m, "BBB_USDT", 100.0, 100)
    m.on_ws_tick("AAA_USDT", 100.0, mono_ms=999_000)
    m.on_ws_tick("BBB_USDT", 100.0, mono_ms=999_000)
    ok1 = await m.on_entry(
        "AAA_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    assert ok1 is True
    ok2 = await m.on_entry(
        "BBB_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    assert ok2 is False
    assert m.last_rejection_reason == "global_limit_full"


# ============================================================ manager: exits


@pytest.mark.asyncio
async def test_exit_on_tp_long() -> None:
    """Entry 100.02 LONG; TP'yi yukari kirdi.

    5s kova kapanisi icin sec_after + 5 beslenir; sec_after = entry_bucket_sec+5,
    kapanis = sec_after+5 = entry_bucket_sec+10 (bir sonraki 5s kovaya gecer).
    """
    m = _manager()
    _warm_ohlcv_1s(m, "BTC_USDT", 100.0, 100)
    m.on_ws_tick("BTC_USDT", 100.0, mono_ms=999_000)
    ok = await m.on_entry(
        "BTC_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    assert ok is True
    pos = m.open_positions["BTC_USDT"]
    tp = pos.tp_price

    # entry_bucket_sec = 1000
    # TP tetikleyen 5s kova: sec_after = 1005
    sec_after = pos.entry_bucket_sec + 5
    m.on_ohlcv(OhlcvSample(
        symbol="BTC_USDT", sec=sec_after, ts_ms=sec_after * 1000,
        open=tp, high=tp + 1.0, low=tp - 0.5, close=tp + 0.5,
    ))
    # 5s kova kapanisi: sec_after + 5 = 1010 (yeni kovaya gecis)
    m.on_ohlcv(OhlcvSample(
        symbol="BTC_USDT", sec=sec_after + 5, ts_ms=(sec_after + 5) * 1000,
        open=tp + 0.5, high=tp + 0.5, low=tp + 0.5, close=tp + 0.5,
    ))
    assert "BTC_USDT" not in m.open_positions
    assert len(m.closed_trades) == 1
    assert m.closed_trades[0].exit_reason == pm.TP


@pytest.mark.asyncio
async def test_exit_on_sl_long() -> None:
    m = _manager()
    _warm_ohlcv_1s(m, "BTC_USDT", 100.0, 100)
    m.on_ws_tick("BTC_USDT", 100.0, mono_ms=999_000)
    ok = await m.on_entry(
        "BTC_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    assert ok is True
    pos = m.open_positions["BTC_USDT"]
    sl = pos.sl_price

    sec_after = pos.entry_bucket_sec + 5
    m.on_ohlcv(OhlcvSample(
        symbol="BTC_USDT", sec=sec_after, ts_ms=sec_after * 1000,
        open=sl, high=sl + 0.5, low=sl - 1.0, close=sl - 0.5,
    ))
    m.on_ohlcv(OhlcvSample(
        symbol="BTC_USDT", sec=sec_after + 5, ts_ms=(sec_after + 5) * 1000,
        open=sl - 0.5, high=sl - 0.5, low=sl - 0.5, close=sl - 0.5,
    ))
    assert "BTC_USDT" not in m.open_positions
    assert m.closed_trades[0].exit_reason == pm.SL


@pytest.mark.asyncio
async def test_exit_sl_wins_over_tp_same_candle() -> None:
    """B2c: ayni mumda hem TP hem SL -> SL konservatif."""
    m = _manager()
    _warm_ohlcv_1s(m, "BTC_USDT", 100.0, 100)
    m.on_ws_tick("BTC_USDT", 100.0, mono_ms=999_000)
    ok = await m.on_entry(
        "BTC_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    assert ok is True
    pos = m.open_positions["BTC_USDT"]
    sl = pos.sl_price
    tp = pos.tp_price

    sec_after = pos.entry_bucket_sec + 5
    # hem SL hem TP'yi tek mumda goster
    m.on_ohlcv(OhlcvSample(
        symbol="BTC_USDT", sec=sec_after, ts_ms=sec_after * 1000,
        open=100.0, high=tp + 1.0, low=sl - 1.0, close=100.0,
    ))
    m.on_ohlcv(OhlcvSample(
        symbol="BTC_USDT", sec=sec_after + 5, ts_ms=(sec_after + 5) * 1000,
        open=100.0, high=100.0, low=100.0, close=100.0,
    ))
    assert m.closed_trades[0].exit_reason == pm.SL


@pytest.mark.asyncio
async def test_entry_bucket_sec_skipped() -> None:
    """Ayni 5s mumda entry'den sonra gelen 1s eventi exit tetiklemez."""
    m = _manager()
    _warm_ohlcv_1s(m, "BTC_USDT", 100.0, 100)
    m.on_ws_tick("BTC_USDT", 100.0, mono_ms=999_000)
    ok = await m.on_entry(
        "BTC_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    assert ok is True
    pos = m.open_positions["BTC_USDT"]
    # entry_bucket_sec = 1000; ayni bucket icinde TP'ye teget at ama kapatma
    tp = pos.tp_price
    m.on_ohlcv(OhlcvSample(
        symbol="BTC_USDT", sec=1001, ts_ms=1001 * 1000,
        open=100.0, high=tp + 1.0, low=100.0, close=100.0,
    ))
    # henuz mum kapanmadi (bucket 1000 hala aktif); pozisyon kapali olmamali
    assert "BTC_USDT" in m.open_positions


# ============================================================ manager: finalize


@pytest.mark.asyncio
async def test_finalize_closes_open_positions() -> None:
    m = _manager()
    _warm_ohlcv_1s(m, "BTC_USDT", 100.0, 100)
    m.on_ws_tick("BTC_USDT", 100.0, mono_ms=999_000)
    await m.on_entry(
        "BTC_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    m.finalize(last_ts_ms=2_000_000, last_prices={"BTC_USDT": 100.5})
    assert len(m.open_positions) == 0
    assert len(m.closed_trades) == 1
    assert m.closed_trades[0].exit_reason == pm.END_OF_BACKTEST


# ============================================================ manager: startup


@pytest.mark.asyncio
async def test_startup_rehydration() -> None:
    """on_startup, DB'deki OPEN pozisyonlari memory'ye yukler."""
    m = _manager()
    _warm_ohlcv_1s(m, "BTC_USDT", 100.0, 100)
    m.on_ws_tick("BTC_USDT", 100.0, mono_ms=999_000)
    await m.on_entry(
        "BTC_USDT", pm.LONG, signal_ts_ms=1_000_000,
        last_price=100.0, mono_ms=1_000_000,
    )
    assert "BTC_USDT" in m.open_positions

    # ayri manager, ayni DB
    m2 = PaperPositionManager(
        _cfg(), m._conn,
        mono_ms_fn=lambda: 1_000_000,
        wall_ms_fn=lambda: 2_000_000,
    )
    m2.setup_db()
    loaded = m2.on_startup()
    assert loaded == 1
    assert "BTC_USDT" in m2.open_positions
    assert m2.open_positions["BTC_USDT"].direction == pm.LONG


# ============================================================ determinism


@pytest.mark.asyncio
async def test_deterministic_repeat() -> None:
    """Ayni input -> ayni trades (determinizm)."""
    async def _run() -> list:
        m = _manager()
        _warm_ohlcv_1s(m, "BTC_USDT", 100.0, 100)
        m.on_ws_tick("BTC_USDT", 100.0, mono_ms=999_000)
        await m.on_entry(
            "BTC_USDT", pm.LONG, signal_ts_ms=1_000_000,
            last_price=100.0, mono_ms=1_000_000,
        )
        pos = m.open_positions["BTC_USDT"]
        tp = pos.tp_price
        sec_after = pos.entry_bucket_sec + 5
        m.on_ohlcv(OhlcvSample(
            symbol="BTC_USDT", sec=sec_after, ts_ms=sec_after * 1000,
            open=tp, high=tp + 1.0, low=tp - 0.5, close=tp + 0.5,
        ))
        m.on_ohlcv(OhlcvSample(
            symbol="BTC_USDT", sec=sec_after + 5, ts_ms=(sec_after + 5) * 1000,
            open=tp + 0.5, high=tp + 0.5, low=tp + 0.5, close=tp + 0.5,
        ))
        return [t.to_dict() for t in m.closed_trades]

    a = await _run()
    b = await _run()
    assert a == b
    assert len(a) == 1