"""B3.5 Mod 2 — observation_state migration wiring into runner._setup_db.

Verifies ShadowRunner._setup_db:
  - runs alerting migration (alert_events, micro_trigger_events)
  - runs observation migration (observation_state, single row id=1)
  - persists PRAGMA user_version = 1
  - is idempotent (second call: no raise, no duplicate row)

Critical: alert_events must be created too — catches the shared
PRAGMA user_version ordering bug (observation first -> alerting skip).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from tests.shadow.runner import ShadowRunner


def _table_names(conn: sqlite3.Connection) -> set:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def test_setup_db_creates_alert_and_observation_tables(
    tmp_path: Path,
) -> None:
    db = tmp_path / "mikov2.sqlite"
    runner = ShadowRunner(["BTC_USDT"], duration_s=0, db_path=db)
    runner._setup_db()
    assert runner._conn is not None
    try:
        tables = _table_names(runner._conn)
        assert "alert_events" in tables
        assert "micro_trigger_events" in tables
        assert "observation_state" in tables
    finally:
        runner._conn.close()


def test_setup_db_sets_user_version_and_single_row(
    tmp_path: Path,
) -> None:
    db = tmp_path / "mikov2.sqlite"
    runner = ShadowRunner(["BTC_USDT"], duration_s=0, db_path=db)
    runner._setup_db()
    assert runner._conn is not None
    try:
        uv = runner._conn.execute("PRAGMA user_version").fetchone()[0]
        assert int(uv) == 1
        n = runner._conn.execute(
            "SELECT COUNT(*) FROM observation_state"
        ).fetchone()[0]
        assert int(n) == 1
        rid = runner._conn.execute(
            "SELECT id FROM observation_state"
        ).fetchone()[0]
        assert int(rid) == 1
    finally:
        runner._conn.close()


def test_setup_db_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "mikov2.sqlite"
    runner = ShadowRunner(["BTC_USDT"], duration_s=0, db_path=db)
    runner._setup_db()
    assert runner._conn is not None
    runner._conn.close()
    runner._setup_db()
    assert runner._conn is not None
    try:
        n = runner._conn.execute(
            "SELECT COUNT(*) FROM observation_state"
        ).fetchone()[0]
        assert int(n) == 1
        uv = runner._conn.execute("PRAGMA user_version").fetchone()[0]
        assert int(uv) == 1
    finally:
        runner._conn.close()