"""Tests for B3.5 Mod 2 T1 observation_state migration."""

import sqlite3

import pytest

from src.observation.migration import (
    OBSERVATION_SCHEMA_VERSION,
    migrate_observation,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    yield c
    c.close()


def _columns(conn: sqlite3.Connection):
    cur = conn.execute("PRAGMA table_info(observation_state)")
    return {row[1]: row for row in cur.fetchall()}


def test_schema_created_with_expected_columns(conn):
    migrate_observation(conn)
    cols = _columns(conn)

    expected = {
        "id",
        "observation_stop",
        "observation_started_at_ms",
        "last_refresh_attempt_ms",
        "last_refresh_success_ms",
        "last_valid_timestamp_ms",
        "checkpoint_due_ms",
        "checkpoint_due_emitted",
        "outage_count",
        "outage_total_ms",
        "last_outage_start_ms",
        "last_outage_end_ms",
        "retention_mode",
        "retention_transition_ms",
        "last_transition_ms",
        "last_transition_reason",
        "clean_shutdown_marker",
        "clean_shutdown_marker_ms",
        "target_days",
        "auto_finalize_done",
        "observation_completed_ms",
    }
    assert expected.issubset(set(cols.keys()))


def test_migration_idempotent(conn):
    assert migrate_observation(conn) == OBSERVATION_SCHEMA_VERSION
    assert migrate_observation(conn) == OBSERVATION_SCHEMA_VERSION

    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == OBSERVATION_SCHEMA_VERSION

    count = conn.execute("SELECT COUNT(*) FROM observation_state").fetchone()[0]
    assert count == 1

    row_id = conn.execute("SELECT id FROM observation_state").fetchone()[0]
    assert row_id == 1


def test_check_id_1_rejects_other(conn):
    migrate_observation(conn)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO observation_state (id) VALUES (2)")
    conn.rollback()


def test_observation_stop_default_and_check(conn):
    migrate_observation(conn)

    value = conn.execute(
        "SELECT observation_stop FROM observation_state WHERE id = 1"
    ).fetchone()[0]
    assert value == 0

    conn.execute(
        "UPDATE observation_state SET observation_stop = 1 WHERE id = 1"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE observation_state SET observation_stop = 2 WHERE id = 1"
        )
    conn.rollback()


def test_clean_shutdown_marker_enum(conn):
    migrate_observation(conn)

    conn.execute(
        "UPDATE observation_state SET clean_shutdown_marker = 'clean' WHERE id = 1"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE observation_state SET clean_shutdown_marker = 'bad' WHERE id = 1"
        )
    conn.rollback()


def test_retention_mode_enum(conn):
    migrate_observation(conn)

    conn.execute(
        "UPDATE observation_state SET retention_mode = 'degraded' WHERE id = 1"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE observation_state SET retention_mode = 'bad' WHERE id = 1"
        )
    conn.rollback()


def test_target_days_default(conn):
    migrate_observation(conn)

    value = conn.execute(
        "SELECT target_days FROM observation_state WHERE id = 1"
    ).fetchone()[0]
    assert value == 60


def test_checkpoint_due_emitted_check(conn):
    migrate_observation(conn)

    conn.execute(
        "UPDATE observation_state SET checkpoint_due_emitted = 1 WHERE id = 1"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE observation_state SET checkpoint_due_emitted = 2 WHERE id = 1"
        )
    conn.rollback()


def test_auto_finalize_done_check(conn):
    migrate_observation(conn)

    conn.execute(
        "UPDATE observation_state SET auto_finalize_done = 1 WHERE id = 1"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE observation_state SET auto_finalize_done = 2 WHERE id = 1"
        )
    conn.rollback()