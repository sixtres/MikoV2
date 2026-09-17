"""
Tests for src.backtest.strategy.
"""

import pytest

from src.backtest.replay_transport import OHLCVEvent, TickerEvent
from src.backtest.signal_detector import (
    DetectorConfig,
    Signal,
    SignalDetector,
    SignalKind,
)
from src.backtest.strategy import (
    Direction,
    EntrySignal,
    Strategy,
    StrategyConfig,
)


def _ev(sec, o, h, l, c):
    return OHLCVEvent(
        sec=sec, ts_ms=sec * 1000,
        open=o, high=h, low=l, close=c,
        buy_vol=0.0, sell_vol=0.0, trade_count=1,
    )


def test_strategy_defaults():
    cfg = StrategyConfig()
    assert cfg.entry_window_ms == 15_000
    assert cfg.min_whale_trust == 0
    assert cfg.cooldown_ms == 60_000
    assert cfg.require_sweep is True
    assert cfg.require_mss is True
    assert cfg.require_fvg is True
    assert cfg.require_ote is False


def test_no_entry_when_no_signals():
    det = SignalDetector(DetectorConfig())
    strat = Strategy(StrategyConfig(), det)
    entries = strat.on_ohlcv(_ev(1000, 100.0, 100.0, 100.0, 100.0))
    assert entries == []


def test_long_entry_aligned_signals():
    det = SignalDetector(DetectorConfig())
    strat = Strategy(StrategyConfig(), det)
    now = 100_000_000
    strat._recent.append((now, Signal(
        kind=SignalKind.SWEEP_DOWN, ts_ms=now, price=100.0)))
    strat._recent.append((now, Signal(
        kind=SignalKind.MSS_UP, ts_ms=now, price=100.0)))
    strat._recent.append((now, Signal(
        kind=SignalKind.FVG_BULLISH, ts_ms=now, price=100.0)))
    entries = strat._try_entry(now, 100.0)
    assert len(entries) == 1
    assert entries[0].direction == Direction.LONG
    assert "long" in entries[0].reason


def test_short_entry_aligned_signals():
    det = SignalDetector(DetectorConfig())
    strat = Strategy(StrategyConfig(), det)
    now = 100_000_000
    strat._recent.append((now, Signal(
        kind=SignalKind.SWEEP_UP, ts_ms=now, price=100.0)))
    strat._recent.append((now, Signal(
        kind=SignalKind.MSS_DOWN, ts_ms=now, price=100.0)))
    strat._recent.append((now, Signal(
        kind=SignalKind.FVG_BEARISH, ts_ms=now, price=100.0)))
    entries = strat._try_entry(now, 100.0)
    assert len(entries) == 1
    assert entries[0].direction == Direction.SHORT


def test_cooldown_blocks_repeat():
    det = SignalDetector(DetectorConfig())
    strat = Strategy(StrategyConfig(cooldown_ms=60_000), det)
    now = 100_000_000
    strat._recent.append((now, Signal(
        kind=SignalKind.SWEEP_DOWN, ts_ms=now, price=100.0)))
    strat._recent.append((now, Signal(
        kind=SignalKind.MSS_UP, ts_ms=now, price=100.0)))
    strat._recent.append((now, Signal(
        kind=SignalKind.FVG_BULLISH, ts_ms=now, price=100.0)))

    e1 = strat._try_entry(now, 100.0)
    assert len(e1) == 1

    # same window, still in cooldown
    strat._recent.append((now + 30_000, Signal(
        kind=SignalKind.SWEEP_DOWN, ts_ms=now + 30_000, price=100.0)))
    e2 = strat._try_entry(now + 30_000, 100.0)
    assert e2 == []

    # after cooldown -> aligned signals tekrar ekle
    later = now + 70_000
    strat._recent.append((later, Signal(
        kind=SignalKind.SWEEP_DOWN, ts_ms=later, price=100.0)))
    strat._recent.append((later, Signal(
        kind=SignalKind.MSS_UP, ts_ms=later, price=100.0)))
    strat._recent.append((later, Signal(
        kind=SignalKind.FVG_BULLISH, ts_ms=later, price=100.0)))
    e3 = strat._try_entry(later, 100.0)
    assert len(e3) == 1


def test_trust_gate_blocks_entry():
    det = SignalDetector(DetectorConfig())
    strat = Strategy(StrategyConfig(min_whale_trust=2), det)
    now = 100_000_000
    strat._recent.append((now, Signal(
        kind=SignalKind.SWEEP_DOWN, ts_ms=now, price=100.0)))
    strat._recent.append((now, Signal(
        kind=SignalKind.MSS_UP, ts_ms=now, price=100.0)))
    strat._recent.append((now, Signal(
        kind=SignalKind.FVG_BULLISH, ts_ms=now, price=100.0)))

    strat._last_trust = 0
    assert strat._try_entry(now, 100.0) == []

    strat._last_trust = 3
    assert len(strat._try_entry(now, 100.0)) == 1


def test_optional_requirements():
    det = SignalDetector(DetectorConfig())
    strat = Strategy(StrategyConfig(
        require_sweep=False, require_mss=False, require_fvg=True
    ), det)
    now = 100_000_000
    strat._recent.append((now, Signal(
        kind=SignalKind.FVG_BULLISH, ts_ms=now, price=100.0)))
    entries = strat._try_entry(now, 100.0)
    assert len(entries) == 1


def test_signal_counts_tracked():
    det = SignalDetector(DetectorConfig())
    strat = Strategy(StrategyConfig(), det)
    strat.signal_counts["SWEEP_UP"] += 1
    strat.signal_counts["SWEEP_UP"] += 1
    assert strat.signal_counts["SWEEP_UP"] == 2


def test_on_ticker_updates_state():
    det = SignalDetector(DetectorConfig())
    strat = Strategy(StrategyConfig(), det)
    ev = TickerEvent(
        ts_ms=1000, last_price=100.0, fair_price=100.0,
        index_price=100.0, hold_vol=1.0, oi_usdt=1_000_000.0,
        funding_rate=0.0001, next_settle_ms=2000,
    )
    strat.on_ticker(ev)
    assert strat._last_oi_usdt == 1_000_000.0
    assert strat._last_funding_rate == 0.0001


def test_no_global_state():
    assert not hasattr(Strategy, "_entries")
    assert not hasattr(Strategy, "_recent")