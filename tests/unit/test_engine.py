"""
Tests for src.backtest.engine.
"""

import pytest

from src.backtest.engine import BacktestEngine, BacktestStats
from src.backtest.replay_transport import (
    DepthEvent,
    OHLCVEvent,
    TickerEvent,
)


class _FakeTransport:
    def __init__(self, events):
        self._events = events

    def stream(self, ts_from, ts_to):
        for e in self._events:
            if ts_from <= e.ts_ms <= ts_to:
                yield e


def _mk_events():
    return [
        OHLCVEvent(sec=1, ts_ms=1000, open=1, high=2, low=0.5, close=1.5,
                   buy_vol=1, sell_vol=1, trade_count=2),
        DepthEvent(ts_ms=2000, version=1, bids=[], asks=[], depth=0),
        TickerEvent(ts_ms=3000, last_price=1.5, fair_price=1.5,
                    index_price=1.5, hold_vol=1, oi_usdt=100, funding_rate=0,
                    next_settle_ms=0),
        OHLCVEvent(sec=4, ts_ms=4000, open=1, high=2, low=0.5, close=1.5,
                   buy_vol=1, sell_vol=1, trade_count=2),
    ]


def test_engine_dispatches_ohlcv():
    transport = _FakeTransport(_mk_events())
    engine = BacktestEngine(transport)
    seen = []
    engine.on_ohlcv(lambda e: seen.append(e.sec))
    stats = engine.run(0, 10_000)
    assert seen == [1, 4]
    assert stats.ohlcv_count == 2
    assert stats.events_total == 4


def test_engine_dispatches_depth():
    transport = _FakeTransport(_mk_events())
    engine = BacktestEngine(transport)
    seen = []
    engine.on_depth(lambda e: seen.append(e.version))
    engine.run(0, 10_000)
    assert seen == [1]


def test_engine_dispatches_ticker():
    transport = _FakeTransport(_mk_events())
    engine = BacktestEngine(transport)
    seen = []
    engine.on_ticker(lambda e: seen.append(e.oi_usdt))
    engine.run(0, 10_000)
    assert seen == [100]


def test_engine_range_filter():
    transport = _FakeTransport(_mk_events())
    engine = BacktestEngine(transport)
    seen = []
    engine.on_ohlcv(lambda e: seen.append(e.sec))
    engine.run(2000, 3000)
    assert seen == []  # no OHLCV in [2000, 3000]


def test_engine_multiple_callbacks():
    transport = _FakeTransport(_mk_events())
    engine = BacktestEngine(transport)
    a, b = [], []
    engine.on_ohlcv(lambda e: a.append(e.sec))
    engine.on_ohlcv(lambda e: b.append(e.sec))
    engine.run(0, 10_000)
    assert a == [1, 4]
    assert b == [1, 4]


def test_engine_callback_error_counted():
    transport = _FakeTransport(_mk_events())
    engine = BacktestEngine(transport)
    def boom(e):
        raise ValueError("boom")
    engine.on_ohlcv(boom)
    stats = engine.run(0, 10_000)
    assert stats.callback_errors == 2
    assert stats.errors_by_type.get("ValueError") == 2


def test_engine_stats_to_dict():
    transport = _FakeTransport(_mk_events())
    engine = BacktestEngine(transport)
    stats = engine.run(0, 10_000)
    d = stats.to_dict()
    assert d["events_total"] == 4
    assert "wall_elapsed_s" in d


def test_engine_no_global_state():
    assert not hasattr(BacktestEngine, "_on_ohlcv")