# YAMA Y-264, Y-265, Y-269, Y-285, Y-341, Y-353, Y-358
# REV7: dashboard sema genisletme testleri

import asyncio
import sqlite3
import time
from pathlib import Path

import pytest

from src.storage.sqlite_writer import SqliteWriter, SqliteWriterConfig


def _make_writer(tmp_path, lock=None):
    if lock is None:
        lock = asyncio.Lock()
    cfg = SqliteWriterConfig(db_path=tmp_path / "test.db")
    writer = SqliteWriter(cfg, lock)
    return writer, cfg


def test_config_defaults(tmp_path):
    cfg = SqliteWriterConfig(db_path=tmp_path / "test.db")
    assert cfg.sqlite_timeout_ms == 5000
    assert cfg.max_retries == 3


@pytest.mark.asyncio
async def test_connect_creates_wal(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    cur = writer._conn.execute("PRAGMA journal_mode")
    assert cur.fetchone()[0].lower() == "wal"
    await writer.close()


@pytest.mark.asyncio
async def test_connect_creates_all_tables(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    cur = writer._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = {r[0] for r in cur.fetchall()}
    assert "positions" in tables
    assert "orders" in tables
    assert "whale_events" in tables
    assert "equity_snapshots" in tables
    assert "daily_stats" in tables
    await writer.close()


@pytest.mark.asyncio
async def test_positions_has_lifecycle_columns(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    cur = writer._conn.execute("PRAGMA table_info(positions)")
    cols = {r[1] for r in cur.fetchall()}
    for expected in (
        "position_id", "symbol", "side", "status", "opened_at_ms",
        "closed_at_ms", "close_reason", "realized_pnl", "fee_total",
        "r_multiple", "qty_open", "qty_remaining", "be_active",
        "trailing_active", "second_entry_count", "whale_trust_score",
        "universe_status",
    ):
        assert expected in cols, "missing column: %s" % expected
    await writer.close()


@pytest.mark.asyncio
async def test_indexes_created(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    cur = writer._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )
    idx = {r[0] for r in cur.fetchall()}
    assert "idx_positions_status" in idx
    assert "idx_whale_symbol_ts" in idx
    assert "idx_equity_ts" in idx
    await writer.close()


@pytest.mark.asyncio
async def test_execute_wal_insert_position(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    await writer.execute_wal(
        {
            "position_id": "pos1",
            "symbol": "BTC_USDT",
            "side": "LONG",
            "avg": 100.0,
            "original_planned_entry": 100.0,
            "original_tp": 110.0,
            "original_sl": 90.0,
            "version": 0,
        }
    )
    rows = await writer.fetch(
        "SELECT position_id, symbol, side FROM positions WHERE position_id=?",
        ("pos1",),
    )
    assert len(rows) == 1
    assert rows[0][1] == "BTC_USDT"
    await writer.close()


@pytest.mark.asyncio
async def test_open_position_and_list(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    await writer.open_position(
        {
            "position_id": "p1",
            "symbol": "BTC_USDT",
            "side": "LONG",
            "avg": 100.0,
            "qty_open": 0.5,
            "original_planned_entry": 100.0,
            "original_tp": 110.0,
            "original_sl": 95.0,
            "whale_trust_score": 3,
            "universe_status": "IN_TOP5",
        }
    )
    rows = await writer.list_open_positions()
    assert len(rows) == 1
    assert rows[0][0] == "p1"
    await writer.close()


@pytest.mark.asyncio
async def test_open_position_idempotent(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    payload = {"position_id": "p1", "symbol": "BTC_USDT", "side": "LONG", "avg": 100.0}
    await writer.open_position(payload)
    await writer.open_position(payload)
    rows = await writer.list_open_positions()
    assert len(rows) == 1
    await writer.close()


@pytest.mark.asyncio
async def test_close_position_sets_outcome(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    await writer.open_position(
        {"position_id": "p1", "symbol": "BTC_USDT", "side": "LONG", "avg": 100.0}
    )
    await writer.close_position(
        "p1", close_reason="TP", realized_pnl=15.5, fee_total=0.4, r_multiple=2.1
    )
    rows = await writer.list_closed_positions()
    assert len(rows) == 1
    assert rows[0][0] == "p1"
    assert rows[0][5] == "TP"
    assert rows[0][7] == 15.5
    open_rows = await writer.list_open_positions()
    assert len(open_rows) == 0
    await writer.close()


@pytest.mark.asyncio
async def test_insert_and_list_whale_events(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    for i in range(3):
        await writer.insert_whale_event(
            {
                "symbol": "BTC_USDT",
                "band_key": "BTC_USDT_%d" % i,
                "price": 50000.0 + i,
                "oi_delta_usd": 60000.0,
                "fill_ratio": 0.5,
                "order_lifetime_ms": 4000,
                "is_real": True,
                "is_spoof": False,
                "trust_score": 2,
                "exchange_ts_ms": 1000 + i,
            }
        )
    rows = await writer.list_recent_whales(limit=10)
    assert len(rows) == 3
    assert rows[0][1] == "BTC_USDT"
    await writer.close()


@pytest.mark.asyncio
async def test_insert_and_list_equity_snapshots(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    now_ms = int(time.time() * 1000)
    for i in range(5):
        await writer.insert_equity_snapshot(
            {
                "ts_ms": now_ms + i * 60000,
                "balance": 1000.0,
                "equity": 1000.0 + i,
                "unrealized_pnl": float(i),
                "realized_today": 0.0,
                "drawdown_pct": 0.0,
                "open_positions": i,
            }
        )
    rows = await writer.list_equity_snapshots(since_ms=now_ms - 1000, limit=100)
    assert len(rows) == 5
    assert rows[0][0] == now_ms
    assert rows[4][0] == now_ms + 4 * 60000
    await writer.close()


@pytest.mark.asyncio
async def test_daily_stats_upsert_and_get(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    await writer.upsert_daily_stats(
        {
            "date_utc": "2026-09-13",
            "start_equity": 1000.0,
            "end_equity": 1015.0,
            "realized_pnl": 15.0,
            "fees": 1.2,
            "trades_count": 5,
            "win_count": 3,
            "loss_count": 2,
        }
    )
    # upsert overwrite
    await writer.upsert_daily_stats(
        {
            "date_utc": "2026-09-13",
            "start_equity": 1000.0,
            "end_equity": 1020.0,
            "realized_pnl": 20.0,
            "fees": 1.5,
            "trades_count": 6,
            "win_count": 4,
            "loss_count": 2,
        }
    )
    row = await writer.get_daily_stats("2026-09-13")
    assert row is not None
    assert row[1] == 1000.0
    assert row[2] == 1020.0
    assert row[5] == 6
    await writer.close()


@pytest.mark.asyncio
async def test_version_optimistic_update(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    await writer.execute_wal({"position_id": "pos1", "avg": 100.0, "version": 0})
    ok = await writer.update_position_versioned("pos1", 101.0, 111.0, 91.0, 1)
    assert ok is True
    v = await writer.get_version("pos1")
    assert v == 1
    # conflict
    ok2 = await writer.update_position_versioned("pos1", 102.0, 112.0, 92.0, 1)
    assert ok2 is False
    await writer.close()


@pytest.mark.asyncio
async def test_close_closes_connection(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    assert writer._conn is not None
    await writer.close()
    assert writer._conn is None


def test_no_global_state():
    import src.storage.sqlite_writer as mod

    assert not hasattr(mod, "_conn")
    assert not hasattr(mod, "_GLOBAL_WRITER")


@pytest.mark.asyncio
async def test_fill_lock_di(tmp_path):
    lock = asyncio.Lock()
    cfg = SqliteWriterConfig(db_path=tmp_path / "test.db")
    writer = SqliteWriter(cfg, lock)
    assert writer._fill_lock is lock
    await writer.connect()
    await writer.execute_wal({"position_id": "p1"})
    await writer.close()