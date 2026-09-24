"""Observation state migration.

B3.5-AI=A:
- wide fixed-schema
- CHECK(id=1)
- NOT NULL DEFAULT
- INSERT OR IGNORE (id=1)
- OR REPLACE YASAK
- mid-phase ALTER TABLE YASAK
- tek migration blok CREATE TABLE IF NOT EXISTS + PRAGMA user_version
- retention yok; tek satır
"""

import sqlite3
from typing import Final

OBSERVATION_SCHEMA_VERSION: Final[int] = 1

_OBSERVATION_STATE_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS observation_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),

    observation_stop INTEGER NOT NULL DEFAULT 0
        CHECK (observation_stop IN (0, 1)),

    observation_started_at_ms INTEGER NOT NULL DEFAULT 0,

    last_refresh_attempt_ms INTEGER NOT NULL DEFAULT 0,
    last_refresh_success_ms INTEGER NOT NULL DEFAULT 0,
    last_valid_timestamp_ms INTEGER NOT NULL DEFAULT 0,

    checkpoint_due_ms INTEGER NOT NULL DEFAULT 0,
    checkpoint_due_emitted INTEGER NOT NULL DEFAULT 0
        CHECK (checkpoint_due_emitted IN (0, 1)),

    outage_count INTEGER NOT NULL DEFAULT 0,
    outage_total_ms INTEGER NOT NULL DEFAULT 0,
    last_outage_start_ms INTEGER NOT NULL DEFAULT 0,
    last_outage_end_ms INTEGER NOT NULL DEFAULT 0,

    retention_mode TEXT NOT NULL DEFAULT 'normal'
        CHECK (retention_mode IN ('normal', 'degraded')),
    retention_transition_ms INTEGER NOT NULL DEFAULT 0,

    last_transition_ms INTEGER NOT NULL DEFAULT 0,
    last_transition_reason TEXT NOT NULL DEFAULT '',

    clean_shutdown_marker TEXT NOT NULL DEFAULT ''
        CHECK (clean_shutdown_marker IN ('', 'clean', 'unclean')),
    clean_shutdown_marker_ms INTEGER NOT NULL DEFAULT 0,

    target_days INTEGER NOT NULL DEFAULT 60,
    auto_finalize_done INTEGER NOT NULL DEFAULT 0
        CHECK (auto_finalize_done IN (0, 1)),
    observation_completed_ms INTEGER NOT NULL DEFAULT 0
);

INSERT OR IGNORE INTO observation_state (id) VALUES (1);
"""


def migrate_observation(conn: sqlite3.Connection) -> int:
    """Create or validate observation_state migration.

    Idempotent: safe to call on every startup.
    Returns current OBSERVATION_SCHEMA_VERSION.
    """
    cur = conn.cursor()

    cur.execute("PRAGMA user_version")
    row = cur.fetchone()
    current = int(row[0]) if row is not None else 0

    if current > OBSERVATION_SCHEMA_VERSION:
        raise RuntimeError(
            "observation schema version "
            f"{current} > supported {OBSERVATION_SCHEMA_VERSION}"
        )

    cur.executescript(_OBSERVATION_STATE_SQL)
    cur.execute(f"PRAGMA user_version = {OBSERVATION_SCHEMA_VERSION}")
    conn.commit()
    return OBSERVATION_SCHEMA_VERSION