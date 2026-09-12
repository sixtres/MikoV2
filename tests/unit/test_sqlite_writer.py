# YAMA Y-264, Y-265, Y-269, Y-285, Y-341, Y-353, Y-358

import asyncio
import sqlite3
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
    mode = cur.fetchone()[0]
    assert mode.lower() == "wal"
    await writer.close()

@pytest.mark.asyncio
async def test_connect_creates_tables(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    cur = writer._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = [r[0] for r in cur.fetchall()]
    assert "positions" in tables
    assert "orders" in tables
    await writer.close()

@pytest.mark.asyncio
async def test_execute_wal_insert(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    payload = {
        "position_id": "pos1",
        "avg": 100.0,
        "original_planned_entry": 100.0,
        "original_tp": 110.0,
        "original_sl": 90.0,
        "current_tp_shifted": 110.0,
        "current_sl_shifted": 90.0,
        "version": 0,
    }
    await writer.execute_wal(payload)
    rows = await writer.fetch("SELECT * FROM positions WHERE position_id=?", ("pos1",))
    assert len(rows) == 1
    await writer.close()

@pytest.mark.asyncio
async def test_fetch_returns_rows(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    await writer.execute_wal({"position_id": "p1", "avg": 1.0})
    await writer.execute_wal({"position_id": "p2", "avg": 2.0})
    rows = await writer.fetch("SELECT position_id FROM positions")
    assert len(rows) == 2
    await writer.close()

@pytest.mark.asyncio
async def test_get_version_initial_zero(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    v = await writer.get_version("nonexist")
    assert v == 0
    await writer.close()

@pytest.mark.asyncio
async def test_update_position_versioned_success(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    await writer.execute_wal(
        {
            "position_id": "pos1",
            "avg": 100.0,
            "version": 0,
        }
    )
    ok = await writer.update_position_versioned("pos1", 101.0, 111.0, 91.0, 1)
    assert ok is True
    v = await writer.get_version("pos1")
    assert v == 1
    await writer.close()

@pytest.mark.asyncio
async def test_update_position_versioned_conflict(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    await writer.execute_wal({"position_id": "pos1", "avg": 100.0, "version": 0})
    # first update to version 1
    await writer.update_position_versioned("pos1", 101.0, 111.0, 91.0, 1)
    # second update with wrong expected version 1 again (old_version 0, but current is 1)
    ok = await writer.update_position_versioned("pos1", 102.0, 112.0, 92.0, 1)
    assert ok is False
    await writer.close()

@pytest.mark.asyncio
async def test_update_position_versioned_increments(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    await writer.execute_wal({"position_id": "pos1", "avg": 100.0, "version": 0})
    await writer.update_position_versioned("pos1", 101.0, 111.0, 91.0, 1)
    await writer.update_position_versioned("pos1", 102.0, 112.0, 92.0, 2)
    v = await writer.get_version("pos1")
    assert v == 2
    await writer.close()

@pytest.mark.asyncio
async def test_immutable_columns_not_updated(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    await writer.execute_wal(
        {
            "position_id": "pos1",
            "avg": 100.0,
            "original_planned_entry": 99.0,
            "original_tp": 110.0,
            "original_sl": 90.0,
            "version": 0,
        }
    )
    await writer.update_position_versioned("pos1", 101.0, 111.0, 91.0, 1)
    rows = await writer.fetch(
        "SELECT original_planned_entry, original_tp, original_sl FROM positions WHERE position_id=?",
        ("pos1",),
    )
    assert rows[0][0] == 99.0
    assert rows[0][1] == 110.0
    assert rows[0][2] == 90.0
    await writer.close()

@pytest.mark.asyncio
async def test_close_closes_connection(tmp_path):
    writer, _ = _make_writer(tmp_path)
    await writer.connect()
    assert writer._conn is not None
    await writer.close()
    assert writer._conn is None

def test_no_global_state():
    from src.storage import sqlite_writer

    assert not hasattr(sqlite_writer.SqliteWriter, "_conn") or isinstance(
        getattr(sqlite_writer.SqliteWriter, "_conn", None), property
    )

@pytest.mark.asyncio
async def test_fill_lock_used(tmp_path):
    lock = asyncio.Lock()
    cfg = SqliteWriterConfig(db_path=tmp_path / "test.db")
    writer = SqliteWriter(cfg, lock)
    assert writer._fill_lock is lock
    await writer.connect()
    await writer.execute_wal({"position_id": "p1"})
    await writer.close()