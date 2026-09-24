"""Observation state single-row access.

B3.5-AI=A kilitli kararlar:
- INSERT OR IGNORE (id=1) tek atış
- OR-REPLACE YASAK
- typed read/write (frozen dataclass)
- torn-read YASAK: tek statement whole-row SELECT
- watchdog 5s poll API (H=C)
- mid-phase ALTER TABLE YASAK
"""

import sqlite3
from dataclasses import dataclass, fields
from typing import Any, Dict, FrozenSet, Union


_ALLOWED_FIELDS: FrozenSet[str] = frozenset({
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
})

_BOOL_FIELDS: FrozenSet[str] = frozenset({
    "observation_stop",
    "checkpoint_due_emitted",
    "auto_finalize_done",
})

_STOP_FLAG_FIELD = "observation_stop"
_ROW_ID = 1


@dataclass(frozen=True)
class ObservationState:
    observation_stop: bool
    observation_started_at_ms: int
    last_refresh_attempt_ms: int
    last_refresh_success_ms: int
    last_valid_timestamp_ms: int
    checkpoint_due_ms: int
    checkpoint_due_emitted: bool
    outage_count: int
    outage_total_ms: int
    last_outage_start_ms: int
    last_outage_end_ms: int
    retention_mode: str
    retention_transition_ms: int
    last_transition_ms: int
    last_transition_reason: str
    clean_shutdown_marker: str
    clean_shutdown_marker_ms: int
    target_days: int
    auto_finalize_done: bool
    observation_completed_ms: int


def _raw_row(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Single-statement whole-row read. Torn-read YASAK."""
    cur = conn.execute(
        "SELECT * FROM observation_state WHERE id = ?", (_ROW_ID,)
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(
            "observation_state row id=1 missing; run migrate_observation first"
        )
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def load_state(conn: sqlite3.Connection) -> ObservationState:
    """Typed whole-row read (single statement)."""
    raw = _raw_row(conn)
    kwargs: Dict[str, Any] = {}
    for f in fields(ObservationState):
        value = raw[f.name]
        kwargs[f.name] = bool(value) if f.name in _BOOL_FIELDS else value
    return ObservationState(**kwargs)


def update_state(conn: sqlite3.Connection, **fields_to_update: Any) -> None:
    """Selective UPDATE. INSERT OR IGNORE (id=1); OR-REPLACE YASAK."""
    if not fields_to_update:
        return

    unknown = set(fields_to_update) - _ALLOWED_FIELDS
    if unknown:
        raise ValueError(
            f"unknown observation_state fields: {sorted(unknown)}"
        )

    # Row garantisi: idempotent, OR-REPLACE değil
    conn.execute(
        "INSERT OR IGNORE INTO observation_state (id) VALUES (?)",
        (_ROW_ID,),
    )

    cols = sorted(fields_to_update.keys())
    assignments = ", ".join(f"{c} = ?" for c in cols)
    values = [fields_to_update[c] for c in cols]
    conn.execute(
        f"UPDATE observation_state SET {assignments} WHERE id = ?",
        [*values, _ROW_ID],
    )
    conn.commit()


def poll_stop_flag(conn: sqlite3.Connection) -> bool:
    """Watchdog 5s poll API (B3.5-H=C). Tek SELECT, torn-read yok."""
    cur = conn.execute(
        "SELECT observation_stop FROM observation_state WHERE id = ?",
        (_ROW_ID,),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(
            "observation_state row id=1 missing; run migrate_observation first"
        )
    return bool(row[0])


def set_stop_flag(conn: sqlite3.Connection, value: Union[bool, int]) -> None:
    """Stop-flag setter. INSERT OR IGNORE (id=1); OR-REPLACE YASAK."""
    conn.execute(
        "INSERT OR IGNORE INTO observation_state (id) VALUES (?)",
        (_ROW_ID,),
    )
    conn.execute(
        "UPDATE observation_state SET observation_stop = ? WHERE id = ?",
        (1 if value else 0, _ROW_ID),
    )
    conn.commit()