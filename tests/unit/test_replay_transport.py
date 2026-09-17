"""
Tests for src.backtest.replay_transport.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from src.backtest.replay_transport import (
    DepthEvent,
    OHLCVEvent,
    ReplayTransport,
    TickerEvent,
)


def _seed_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_replay.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE trades_ohlcv_1s (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, sec INTEGER,
            open REAL, high REAL, low REAL, close REAL,
            buy_vol REAL, sell_vol REAL, trade_count INTEGER
        );
        CREATE TABLE orderbook_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_ms INTEGER, symbol TEXT, version INTEGER,
            bids_json TEXT, asks_json TEXT, depth INTEGER
        );
        CREATE TABLE tickers_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_ms INTEGER, symbol TEXT,
            last_price REAL, fair_price REAL, index_price REAL,
            hold_vol REAL, oi_usdt REAL, funding_rate REAL,
            next_settle_ms INTEGER
        );
        """
    )
    for i in range(5):
        sec = 1000 + i
        conn.execute(
            "INSERT INTO trades_ohlcv_1s (symbol, sec, open, high, low, close, "
            "buy_vol, sell_vol, trade_count) VALUES (?,?,?,?,?,?,?,?,?)",
            ("BTC_USDT", sec, 100.0, 101.0, 99.0, 100.5, 10.0, 5.0, 3),
        )
    for i in range(2):
        ts = 1000 * 1000 + i * 3000
        conn.execute(
            "INSERT INTO orderbook_snapshots (timestamp_ms, symbol, version, "
            "bids_json, asks_json, depth) VALUES (?,?,?,?,?,?)",
            (ts, "BTC_USDT", 100 + i,
             json.dumps([[100.0, 1.0], [99.0, 2.0]]),
             json.dumps([[101.0, 1.5], [102.0, 2.5]]),
             2),
        )
    conn.execute(
        "INSERT INTO tickers_snapshot (ts_ms, symbol, last_price, fair_price, "
        "index_price, hold_vol, oi_usdt, funding_rate, next_settle_ms) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (1000_500, "BTC_USDT", 100.5, 100.6, 100.7, 1000.0, 100000.0, 0.0001, 2000_000),
    )
    conn.commit()
    conn.close()
    return db_path


def test_stream_empty_range(tmp_path):
    db_path = _seed_db(tmp_path)
    t = ReplayTransport(db_path)
    out = list(t.stream(9_999_999, 10_000_000))
    assert out == []


def test_stream_yields_ordered(tmp_path):
    db_path = _seed_db(tmp_path)
    t = ReplayTransport(db_path)
    events = list(t.stream(0, 9_999_999_999))
    ts_list = [e.ts_ms for e in events]
    assert ts_list == sorted(ts_list)
    assert len(events) == 5 + 2 + 1


def test_ohlcv_event_fields(tmp_path):
    db_path = _seed_db(tmp_path)
    t = ReplayTransport(db_path)
    events = [e for e in t.stream(0, 9_999_999_999) if isinstance(e, OHLCVEvent)]
    assert len(events) == 5
    e = events[0]
    assert e.sec == 1000
    assert e.ts_ms == 1_000_000
    assert e.open == 100.0
    assert e.trade_count == 3


def test_depth_event_json_parsed(tmp_path):
    db_path = _seed_db(tmp_path)
    t = ReplayTransport(db_path)
    events = [e for e in t.stream(0, 9_999_999_999) if isinstance(e, DepthEvent)]
    assert len(events) == 2
    e = events[0]
    assert e.bids[0] == [100.0, 1.0]
    assert e.asks[0] == [101.0, 1.5]
    assert e.depth == 2


def test_ticker_event_fields(tmp_path):
    db_path = _seed_db(tmp_path)
    t = ReplayTransport(db_path)
    events = [e for e in t.stream(0, 9_999_999_999) if isinstance(e, TickerEvent)]
    assert len(events) == 1
    e = events[0]
    assert e.ts_ms == 1_000_500
    assert e.oi_usdt == 100_000.0
    assert e.funding_rate == 0.0001


def test_get_time_range(tmp_path):
    db_path = _seed_db(tmp_path)
    t = ReplayTransport(db_path)
    rng = t.get_time_range()
    assert rng is not None
    lo, hi = rng
    assert lo == 1_000_000
    assert hi == 1_004_000


def test_get_time_range_empty(tmp_path):
    db_path = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE trades_ohlcv_1s (symbol TEXT, sec INTEGER,
          open REAL, high REAL, low REAL, close REAL,
          buy_vol REAL, sell_vol REAL, trade_count INTEGER);
        CREATE TABLE orderbook_snapshots (timestamp_ms INTEGER, symbol TEXT,
          version INTEGER, bids_json TEXT, asks_json TEXT, depth INTEGER);
        CREATE TABLE tickers_snapshot (ts_ms INTEGER, symbol TEXT,
          last_price REAL, fair_price REAL, index_price REAL,
          hold_vol REAL, oi_usdt REAL, funding_rate REAL, next_settle_ms INTEGER);
        """
    )
    conn.commit()
    conn.close()
    t = ReplayTransport(db_path)
    assert t.get_time_range() is None


def test_no_global_state():
    assert not hasattr(ReplayTransport, "_conn")