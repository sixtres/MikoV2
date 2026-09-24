"""Tests for B3.5 Mod 2 T2 observation_state single-row access."""

import inspect
import sqlite3
from dataclasses import fields

import pytest

from src.observation import state as state_mod
from src.observation.migration import migrate_observation
from src.observation.state import (
    ObservationState,
    load_state,
    poll_stop_flag,
    set_stop_flag,
    update_state,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    migrate_observation(c)
    yield c
    c.close()


def test_load_state_returns_typed_dataclass(conn):
    s = load_state(conn)
    assert isinstance(s, ObservationState)
    assert isinstance(s.observation_stop, bool)
    assert isinstance(s.target_days, int)


def test_load_state_defaults(conn):
    s = load_state(conn)
    assert s.observation_stop is False
    assert s.observation_started_at_ms == 0
    assert s.checkpoint_due_emitted is False
    assert s.retention_mode == "normal"
    assert s.clean_shutdown_marker == ""
    assert s.target_days == 60
    assert s.auto_finalize_done is False


def test_update_state_selective_persists(conn):
    update_state(conn, target_days=45, retention_mode="degraded")
    s = load_state(conn)
    assert s.target_days == 45
    assert s.retention_mode == "degraded"
    # Diğer alanlar default kalır
    assert s.observation_stop is False


def test_update_state_rejects_unknown_field(conn):
    with pytest.raises(ValueError):
        update_state(conn, nonexistent_field=1)


def test_update_state_no_op_on_empty(conn):
    # Boş çağrı sessizce döner; yeni satır açmaz/bozmaz
    update_state(conn)
    count = conn.execute(
        "SELECT COUNT(*) FROM observation_state"
    ).fetchone()[0]
    assert count == 1


def test_insert_or_ignore_keeps_single_row(conn):
    for _ in range(5):
        update_state(conn, target_days=30)
    count = conn.execute(
        "SELECT COUNT(*) FROM observation_state"
    ).fetchone()[0]
    assert count == 1
    assert conn.execute(
        "SELECT id FROM observation_state"
    ).fetchone()[0] == 1


def test_no_or_replace_in_module_source():
    import ast

    src = inspect.getsource(state_mod)
    tree = ast.parse(src)

    # Yorumlar ast'te yer almaz; docstring'ler string literal olduğu için
    # taranır ve OR-REPLACE (tire) yazımıyla geçer. Yalnızca SQL keyword
    # içeren string literal'lerde "OR REPLACE" (boşluk) yasak.
    sql_keywords = ("INSERT", "UPDATE", "SELECT", "CREATE")

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if any(kw in v.upper() for kw in sql_keywords):
                assert "OR REPLACE" not in v.upper(), (
                    f"SQL literal içinde OR REPLACE yasak: {v!r}"
                )


def test_poll_stop_flag_default_and_roundtrip(conn):
    assert poll_stop_flag(conn) is False
    set_stop_flag(conn, True)
    assert poll_stop_flag(conn) is True
    set_stop_flag(conn, False)
    assert poll_stop_flag(conn) is False


def test_set_stop_flag_idempotent_single_row(conn):
    set_stop_flag(conn, True)
    set_stop_flag(conn, True)
    count = conn.execute(
        "SELECT COUNT(*) FROM observation_state"
    ).fetchone()[0]
    assert count == 1


def test_dataclass_fields_match_schema_columns(conn):
    cur = conn.execute("PRAGMA table_info(observation_state)")
    schema_cols = {row[1] for row in cur.fetchall()}
    schema_cols.discard("id")
    dc_fields = {f.name for f in fields(ObservationState)}
    assert dc_fields == schema_cols


def test_check_id_1_invariant_preserved(conn):
    # CHECK(id=1) hâlâ aktif: farklı id eklenemez
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO observation_state (id) VALUES (2)")
    conn.rollback()