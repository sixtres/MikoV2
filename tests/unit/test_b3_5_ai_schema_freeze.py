"""T5: B3.5-AI=A schema freeze absorb testleri.

9 kilitli karar (H,K,T,R,AB,W,AD,AE,S) observation_state
şemasında açık kolon olarak taşınmalı. Mid-phase ALTER YASAK.
"""

import sqlite3
from dataclasses import fields

import pytest

from src.observation.migration import migrate_observation
from src.observation.state import ObservationState


# Karar -> zorunlu kolonlar (B3.5 Mod 1 Round 1-4)
DECISION_MAP = {
    "H":  ["observation_stop"],
    "K":  ["id"],
    "T":  ["outage_count", "outage_total_ms",
           "last_outage_start_ms", "last_outage_end_ms"],
    "R":  ["checkpoint_due_ms", "checkpoint_due_emitted"],
    "AB": ["retention_mode", "retention_transition_ms"],
    "W":  ["last_transition_ms", "last_transition_reason"],
    "AD": ["clean_shutdown_marker", "clean_shutdown_marker_ms"],
    "AE": ["target_days", "auto_finalize_done",
           "observation_completed_ms"],
    "S":  ["observation_started_at_ms", "last_refresh_attempt_ms",
           "last_refresh_success_ms", "last_valid_timestamp_ms"],
}

# Freeze sonrası kolon sayısı (id + 20 alan) — mid-phase ALTER regresyonu
_EXPECTED_COLUMN_COUNT = 21


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    migrate_observation(c)
    yield c
    c.close()


def _cols(conn):
    cur = conn.execute("PRAGMA table_info(observation_state)")
    return {row[1] for row in cur.fetchall()}


def _col_info(conn):
    cur = conn.execute("PRAGMA table_info(observation_state)")
    return {row[1]: {"type": row[2].upper(), "notnull": row[3],
                     "dflt": row[4]} for row in cur.fetchall()}


def test_all_nine_decisions_absorbed(conn):
    cols = _cols(conn)
    for decision, required in DECISION_MAP.items():
        missing = set(required) - cols
        assert not missing, f"{decision} kararı eksik: {missing}"


def test_H_stop_flag_integer_notnull_default_0(conn):
    info = _col_info(conn)["observation_stop"]
    assert info["type"] == "INTEGER"
    assert info["notnull"] == 1
    assert info["dflt"] == "0"


def test_K_single_row_check_id_1(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO observation_state (id) VALUES (2)")
    conn.rollback()
    sql = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type='table' AND name='observation_state'"
    ).fetchone()[0]
    assert "CHECK (id = 1)" in sql or "CHECK(id = 1)" in sql \
        or "CHECK (id=1)" in sql or "CHECK(id=1)" in sql


def test_T_outage_columns_integer_notnull(conn):
    info = _col_info(conn)
    for c in DECISION_MAP["T"]:
        assert info[c]["type"] == "INTEGER"
        assert info[c]["notnull"] == 1
        assert info[c]["dflt"] == "0"


def test_R_checkpoint_due_columns(conn):
    info = _col_info(conn)
    assert info["checkpoint_due_ms"]["type"] == "INTEGER"
    assert info["checkpoint_due_emitted"]["type"] == "INTEGER"
    assert info["checkpoint_due_emitted"]["dflt"] == "0"


def test_AB_retention_enum_columns(conn):
    info = _col_info(conn)
    assert info["retention_mode"]["type"] == "TEXT"
    assert info["retention_mode"]["dflt"] == "'normal'"
    assert info["retention_transition_ms"]["type"] == "INTEGER"


def test_W_transition_columns(conn):
    info = _col_info(conn)
    assert info["last_transition_ms"]["type"] == "INTEGER"
    assert info["last_transition_reason"]["type"] == "TEXT"


def test_AD_clean_shutdown_marker_columns(conn):
    info = _col_info(conn)
    assert info["clean_shutdown_marker"]["type"] == "TEXT"
    assert info["clean_shutdown_marker"]["dflt"] == "''"
    assert info["clean_shutdown_marker_ms"]["type"] == "INTEGER"


def test_AE_auto_finalize_columns(conn):
    info = _col_info(conn)
    assert info["target_days"]["type"] == "INTEGER"
    assert info["target_days"]["dflt"] == "60"
    assert info["auto_finalize_done"]["type"] == "INTEGER"
    assert info["auto_finalize_done"]["dflt"] == "0"
    assert info["observation_completed_ms"]["type"] == "INTEGER"


def test_S_retain_last_valid_columns(conn):
    info = _col_info(conn)
    for c in DECISION_MAP["S"]:
        assert info[c]["type"] == "INTEGER"
        assert info[c]["notnull"] == 1


def test_clean_shutdown_marker_enum_check(conn):
    conn.execute(
        "UPDATE observation_state SET clean_shutdown_marker='clean' WHERE id=1"
    )
    conn.commit()
    for good in ("clean", "unclean", ""):
        conn.execute(
            "UPDATE observation_state SET clean_shutdown_marker=? WHERE id=1",
            (good,),
        )
        conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE observation_state SET clean_shutdown_marker='x' WHERE id=1"
        )
    conn.rollback()


def test_retention_mode_enum_check(conn):
    for good in ("normal", "degraded"):
        conn.execute(
            "UPDATE observation_state SET retention_mode=? WHERE id=1",
            (good,),
        )
        conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE observation_state SET retention_mode='x' WHERE id=1"
        )
    conn.rollback()


def test_no_mid_phase_alter_regression(conn):
    # Freeze sonrası kolon sayısı sabit
    cols = _cols(conn)
    assert len(cols) == _EXPECTED_COLUMN_COUNT


def test_dataclass_matches_schema_columns(conn):
    schema_cols = _cols(conn)
    schema_cols.discard("id")
    dc_fields = {f.name for f in fields(ObservationState)}
    assert dc_fields == schema_cols


def test_boolean_fields_roundtrip(conn):
    from src.observation.state import load_state, update_state
    update_state(conn, observation_stop=1, checkpoint_due_emitted=1,
                 auto_finalize_done=1)
    s = load_state(conn)
    assert s.observation_stop is True
    assert s.checkpoint_due_emitted is True
    assert s.auto_finalize_done is True