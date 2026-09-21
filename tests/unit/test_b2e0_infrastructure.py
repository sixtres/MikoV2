# tests/unit/test_b2e0_infrastructure.py
# B2e.0 — event symbol + multi-symbol stream + per-symbol sim state +
#         finalize dict + MTM + data quality (SORU A' ayri faz)

from __future__ import annotations

import sqlite3

import pytest

from src.backtest.data_quality import analyze_ohlcv_secs
from src.backtest.position_sim import (
    ExitReason,
    PositionSimConfig,
    PositionSimulator,
)
from src.backtest.replay_transport import (
    DepthEvent,
    OHLCVEvent,
    ReplayTransport,
    TickerEvent,
)
from src.backtest.strategy import Direction, EntrySignal


# ============================================================ events

def test_ohlcv_event_default_symbol():
    ev = OHLCVEvent(
        sec=1, ts_ms=1000, open=1.0, high=1.1, low=0.9, close=1.0,
        buy_vol=0.0, sell_vol=0.0, trade_count=1,
    )
    assert ev.symbol == "BTC_USDT"
    assert ev.source_seq == 0


def test_ohlcv_event_explicit_symbol_and_seq():
    ev = OHLCVEvent(
        sec=100, ts_ms=100000, open=1.0, high=1.1, low=0.9, close=1.0,
        buy_vol=0.0, sell_vol=0.0, trade_count=1,
        symbol="ETH_USDT", source_seq=100,
    )
    assert ev.symbol == "ETH_USDT"
    assert ev.source_seq == 100


def test_depth_event_default_symbol():
    ev = DepthEvent(ts_ms=1, version=1, bids=[], asks=[], depth=0)
    assert ev.symbol == "BTC_USDT"
    assert ev.source_seq == 0


def test_ticker_event_default_symbol():
    ev = TickerEvent(
        ts_ms=1, last_price=1.0, fair_price=1.0, index_price=1.0,
        hold_vol=0.0, oi_usdt=0.0, funding_rate=0.0, next_settle_ms=0,
    )
    assert ev.symbol == "BTC_USDT"
    assert ev.source_seq == 0


# ============================================================ stream

@pytest.fixture
def tiny_db(tmp_path):
    p = tmp_path / "tiny.sqlite"
    conn = sqlite3.connect(str(p))
    conn.executescript("""
        CREATE TABLE trades_ohlcv_1s (
            symbol TEXT, sec INTEGER,
            open REAL, high REAL, low REAL, close REAL,
            buy_vol REAL, sell_vol REAL, trade_count INTEGER
        );
        CREATE TABLE orderbook_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, timestamp_ms INTEGER, version INTEGER,
            bids_json TEXT, asks_json TEXT, depth INTEGER
        );
        CREATE TABLE tickers_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, ts_ms INTEGER, last_price REAL, fair_price REAL,
            index_price REAL, hold_vol REAL, oi_usdt REAL,
            funding_rate REAL, next_settle_ms INTEGER
        );
    """)
    rows_ohlcv = [
        ("BTC_USDT", 100, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1),
        ("ETH_USDT", 100, 2.0, 2.0, 2.0, 2.0, 0.0, 0.0, 1),
        ("BTC_USDT", 101, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1),
        ("ETH_USDT", 101, 2.0, 2.0, 2.0, 2.0, 0.0, 0.0, 1),
    ]
    conn.executemany(
        "INSERT INTO trades_ohlcv_1s VALUES (?,?,?,?,?,?,?,?,?)", rows_ohlcv
    )
    conn.execute(
        "INSERT INTO orderbook_snapshots "
        "(symbol, timestamp_ms, version, bids_json, asks_json, depth) "
        "VALUES (?,?,?,?,?,?)",
        ("BTC_USDT", 100000, 1, "[]", "[]", 0),
    )
    conn.execute(
        "INSERT INTO tickers_snapshot "
        "(symbol, ts_ms, last_price, fair_price, index_price, hold_vol, "
        " oi_usdt, funding_rate, next_settle_ms) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        ("BTC_USDT", 100000, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0001, 0),
    )
    conn.execute(
        "INSERT INTO tickers_snapshot "
        "(symbol, ts_ms, last_price, fair_price, index_price, hold_vol, "
        " oi_usdt, funding_rate, next_settle_ms) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        ("ETH_USDT", 100000, 2.0, 2.0, 2.0, 0.0, 0.0, 0.0001, 0),
    )
    conn.commit()
    conn.close()
    return p


def test_stream_multi_tie_break(tiny_db):
    t = ReplayTransport(tiny_db)
    evs = list(t.stream_multi(["BTC_USDT", "ETH_USDT"], 0, 10**13))
    # ts=100000 icin beklenen sira (SORU J'):
    #   OHLCV BTC, OHLCV ETH, Depth BTC, Ticker BTC, Ticker ETH
    ts100 = [e for e in evs if e.ts_ms == 100000]
    kinds = []
    for e in ts100:
        if isinstance(e, OHLCVEvent):
            kinds.append(("OHLCV", e.symbol))
        elif isinstance(e, DepthEvent):
            kinds.append(("Depth", e.symbol))
        else:
            kinds.append(("Ticker", e.symbol))
    assert kinds == [
        ("OHLCV", "BTC_USDT"),
        ("OHLCV", "ETH_USDT"),
        ("Depth", "BTC_USDT"),
        ("Ticker", "BTC_USDT"),
        ("Ticker", "ETH_USDT"),
    ]


def test_stream_multi_source_seq_from_db(tiny_db):
    t = ReplayTransport(tiny_db)
    evs = list(t.stream_multi(["BTC_USDT"], 0, 10**13))
    for e in evs:
        if isinstance(e, OHLCVEvent):
            assert e.source_seq == e.sec
        elif isinstance(e, DepthEvent):
            assert e.source_seq >= 1  # AUTOINCREMENT id
        elif isinstance(e, TickerEvent):
            assert e.source_seq >= 1


def test_stream_single_backward_compat(tiny_db):
    t = ReplayTransport(tiny_db, symbol="BTC_USDT")
    evs = list(t.stream(0, 10**13))
    for e in evs:
        assert e.symbol == "BTC_USDT"


# ============================================================ position_sim

def _ohlcv(sym, sec, o, h, l, c):
    return OHLCVEvent(
        sec=sec, ts_ms=sec * 1000, open=o, high=h, low=l, close=c,
        buy_vol=0.0, sell_vol=0.0, trade_count=1, symbol=sym,
    )


def _entry(direction, ts_ms, price):
    return EntrySignal(
        direction=direction, ts_ms=ts_ms, price=price,
        reason="test", signals=(),
    )


def _warm(sim, sym, start_sec, n, price=100.0, half_range=0.5):
    sec = start_sec
    last = sec
    for _ in range(n):
        sim.on_ohlcv(_ohlcv(sym, sec, price, price + half_range,
                            price - half_range, price))
        last = sec
        sec += 5
    return last


def test_candles_are_isolated_per_symbol():
    sim = PositionSimulator(PositionSimConfig())
    _warm(sim, "BTC_USDT", 1000, 25, price=100.0, half_range=0.5)
    # ETH hic beslenmedi → ATR None
    assert sim._atr("ETH_USDT") is None
    assert sim._atr("BTC_USDT") is not None


def test_global_limit_with_multi_symbols():
    sim = PositionSimulator(PositionSimConfig(max_positions_global=2))
    _warm(sim, "BTC_USDT", 1000, 25)
    _warm(sim, "ETH_USDT", 1000, 25)
    _warm(sim, "SOL_USDT", 1000, 25)
    ts = (1000 + 25 * 5) * 1000
    assert sim.on_entry(_entry(Direction.LONG, ts, 100.0), "BTC_USDT")
    assert sim.on_entry(_entry(Direction.SHORT, ts, 100.0), "ETH_USDT")
    assert not sim.on_entry(_entry(Direction.LONG, ts, 100.0), "SOL_USDT")


def test_finalize_uses_last_prices_dict():
    sim = PositionSimulator(PositionSimConfig(fee_taker=0.0, fee_maker=0.0))
    _warm(sim, "BTC_USDT", 1000, 25)
    ts_ms = (1000 + 25 * 5) * 1000
    sim.on_entry(_entry(Direction.LONG, ts_ms, 100.0), "BTC_USDT")
    # Ayni bucket'ta kapatma; sonra finalize dict ile 105.0 fiyat
    sim.finalize(last_ts_ms=ts_ms + 60_000,
                 last_prices={"BTC_USDT": 105.0})
    assert len(sim.trades) == 1
    t = sim.trades[0]
    assert t.exit_reason == ExitReason.END_OF_BACKTEST
    assert t.exit_price == 105.0


def test_finalize_dict_falls_back_to_last_seen_price():
    sim = PositionSimulator(PositionSimConfig(fee_taker=0.0, fee_maker=0.0))
    _warm(sim, "BTC_USDT", 1000, 25)
    ts_ms = (1000 + 25 * 5) * 1000
    sim.on_entry(_entry(Direction.LONG, ts_ms, 100.0), "BTC_USDT")
    # Sembol icin son gorulen fiyat 100.0 (warm'dan); dict bos
    sim.finalize(last_ts_ms=ts_ms + 60_000, last_prices={})
    assert sim.trades[0].exit_price == pytest.approx(100.0)


def test_funding_timeline_per_symbol():
    cfg = PositionSimConfig(include_funding=True, fee_taker=0.0, fee_maker=0.0)
    sim = PositionSimulator(cfg)
    # BTC icin funding rate yok; ETH icin var
    sim.on_ticker(TickerEvent(
        ts_ms=1, last_price=100.0, fair_price=100.0, index_price=100.0,
        hold_vol=0.0, oi_usdt=0.0, funding_rate=0.0001, next_settle_ms=0,
        symbol="ETH_USDT",
    ))
    # BTC _last_funding_rate'da kayit yok
    assert "BTC_USDT" not in sim._last_funding_rate
    assert sim._last_funding_rate["ETH_USDT"] == 0.0001


def test_mtm_equity_includes_unrealized():
    sim = PositionSimulator(PositionSimConfig(fee_taker=0.0, fee_maker=0.0))
    last = _warm(sim, "BTC_USDT", 1000, 25, price=100.0, half_range=0.5)
    ts_ms = (last + 5) * 1000
    sim.on_entry(_entry(Direction.LONG, ts_ms, 100.0), "BTC_USDT")
    # sonraki 1s event: fiyat 110 (TP'ye varmadan, MTM)
    sim.on_ohlcv(_ohlcv("BTC_USDT", last + 5, 100.0, 110.5, 99.5, 110.0))
    eq_mtm = sim.equity
    assert eq_mtm > sim._realized_equity  # unrealized kâr yansıdı


def test_mtm_equity_equals_realized_when_flat():
    sim = PositionSimulator(PositionSimConfig())
    _warm(sim, "BTC_USDT", 1000, 25)
    assert sim.equity == sim._realized_equity


# ============================================================ data_quality

def test_data_quality_empty():
    r = analyze_ohlcv_secs("BTC_USDT", [])
    assert r.sample_count == 0
    assert r.completeness == 0.0
    assert r.gap_count == 0


def test_data_quality_no_gaps():
    r = analyze_ohlcv_secs("BTC_USDT", [10, 11, 12, 13, 14])
    assert r.span_sec == 4
    assert r.sample_count == 5
    assert r.expected_count == 5
    assert r.completeness == 1.0
    assert r.gap_count == 0
    assert r.max_gap_sec == 0


def test_data_quality_with_gaps():
    # her delta > 1 → gap:
    #   12 -> 20 (8), 21 -> 30 (9), 30 -> 45 (15)
    secs = [10, 11, 12, 20, 21, 30, 45]
    r = analyze_ohlcv_secs("BTC_USDT", secs)
    assert r.gap_count == 3
    assert r.max_gap_sec == 15
    assert r.gaps == ((12, 20), (21, 30), (30, 45))


def test_data_quality_completeness_known():
    # span 0..9, beklenen 10, 7 ornek → 0.7
    secs = [0, 1, 2, 3, 4, 5, 9]
    r = analyze_ohlcv_secs("BTC_USDT", secs)
    assert r.expected_count == 10
    assert r.completeness == pytest.approx(0.7)