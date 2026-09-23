# tests/unit/test_alerting_migration.py
"""B3.4 Mod 2 — migration tablo / şema / retention testleri (T1)."""
from __future__ import annotations

import sqlite3

import pytest

from src.alerting.migration import (
    ALERT_EVENTS_RETENTION_MS,
    DELIVERY_STATUSES,
    MICRO_TRIGGER_RETENTION_MS,
    SCHEMA_VERSION,
    chunked_delete_older_than,
    run_migration,
)


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    yield c
    c.close()


def test_migration_sets_user_version(conn):
    v = run_migration(conn)
    assert v == SCHEMA_VERSION
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_migration_idempotent(conn):
    run_migration(conn)
    run_migration(conn)
    run_migration(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_tables_exist(conn):
    run_migration(conn)
    names = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "alert_events" in names
    assert "micro_trigger_events" in names


def test_indexes_exist(conn):
    run_migration(conn)
    names = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
    }
    assert "idx_alert_events_status_ts" in names
    assert "idx_alert_events_ts" in names
    assert "idx_micro_trigger_symbol_ts" in names
    assert "idx_micro_trigger_ts" in names


def test_delivery_status_five_values_accepted(conn):
    run_migration(conn)
    for st in DELIVERY_STATUSES:
        conn.execute(
            "INSERT INTO alert_events"
            "(ts_ms,event_type,severity,created_at_ms,delivery_status)"
            " VALUES(?,?,?,?,?)",
            (1, "TRIGGER", "WARNING", 1, st),
        )
    conn.commit()
    got = {
        r[0]
        for r in conn.execute("SELECT delivery_status FROM alert_events")
    }
    assert got == set(DELIVERY_STATUSES)


def test_delivery_status_invalid_rejected(conn):
    run_migration(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO alert_events"
            "(ts_ms,event_type,severity,created_at_ms,delivery_status)"
            " VALUES(?,?,?,?,?)",
            (1, "TRIGGER", "WARNING", 1, "bogus"),
        )


def test_micro_trigger_events_insertable(conn):
    run_migration(conn)
    conn.execute(
        "INSERT INTO micro_trigger_events(ts_ms,symbol,event_type)"
        " VALUES(?,?,?)",
        (10, "BTC_USDT", "SWEEP"),
    )
    conn.commit()
    row = conn.execute(
        "SELECT symbol, event_type, state_from, state_to"
        " FROM micro_trigger_events"
    ).fetchone()
    assert row == ("BTC_USDT", "SWEEP", None, None)


def test_chunked_delete_unknown_table(conn):
    run_migration(conn)
    with pytest.raises(ValueError):
        chunked_delete_older_than(conn, "positions", 0)


def test_chunked_delete_chunk_range(conn):
    run_migration(conn)
    with pytest.raises(ValueError):
        chunked_delete_older_than(conn, "alert_events", 0, chunk=0)
    with pytest.raises(ValueError):
        chunked_delete_older_than(conn, "alert_events", 0, chunk=100000)


def test_chunked_delete_rows(conn):
    run_migration(conn)
    rows = [(i, "TRIGGER", "WARNING", i) for i in range(20)]
    conn.executemany(
        "INSERT INTO alert_events"
        "(ts_ms,event_type,severity,created_at_ms) VALUES(?,?,?,?)",
        rows,
    )
    conn.commit()
    deleted = chunked_delete_older_than(
        conn, "alert_events", cutoff_ms=10, chunk=3
    )
    assert deleted == 10
    remaining = conn.execute(
        "SELECT COUNT(*) FROM alert_events"
    ).fetchone()[0]
    assert remaining == 10


def test_chunked_delete_micro_trigger(conn):
    run_migration(conn)
    rows = [(i, "BTC_USDT", "SWEEP") for i in range(7)]
    conn.executemany(
        "INSERT INTO micro_trigger_events(ts_ms,symbol,event_type)"
        " VALUES(?,?,?)",
        rows,
    )
    conn.commit()
    deleted = chunked_delete_older_than(
        conn, "micro_trigger_events", cutoff_ms=3, chunk=2
    )
    assert deleted == 3


def test_retention_constants():
    assert MICRO_TRIGGER_RETENTION_MS == 3 * 24 * 3600 * 1000
    assert ALERT_EVENTS_RETENTION_MS == 7 * 24 * 3600 * 1000
    assert ALERT_EVENTS_RETENTION_MS > MICRO_TRIGGER_RETENTION_MS