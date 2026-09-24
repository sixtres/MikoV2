"""B3.5 M=B — /api/v2/observation endpoint (DashboardRoutes.observation).

Salt-okuma. DB baglantisi DI ile gelir (Y-353). status alani
observation_stop / auto_finalize_done'dan turetilir.

Test review: tests/unit/test_dashboard_routes.py — no change required
(constructor'a keyword-only `conn=None` eklendi; mevcut testler
pozisyonel args ile cagiriyor, kirilma yok). app.py port degisikligi
davranis degistirdigi icin test_dashboard_app.py patchi bu teslimde.
"""
from __future__ import annotations

import asyncio
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dashboard.routes import DashboardRoutes, RoutesConfig
from src.observation import migrate_observation
from src.observation.state import set_stop_flag, update_state


def _fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    migrate_observation(conn)
    return conn


def _make_routes(conn, **cfg_over) -> DashboardRoutes:
    cfg = RoutesConfig(**cfg_over)
    sqlite = MagicMock()
    sqlite.fetch = AsyncMock(return_value=[[0]])
    lock = asyncio.Lock()
    return DashboardRoutes(cfg, sqlite, lock, conn=conn)


@pytest.mark.asyncio
async def test_observation_no_conn_returns_error():
    cfg = RoutesConfig()
    sqlite = MagicMock()
    sqlite.fetch = AsyncMock(return_value=[[0]])
    lock = asyncio.Lock()
    r = DashboardRoutes(cfg, sqlite, lock)  # conn default None
    result = await r.observation()
    assert result == {"error": "no_db_connection"}


@pytest.mark.asyncio
async def test_observation_returns_active_status():
    conn = _fresh_conn()
    try:
        r = _make_routes(conn)
        result = await r.observation()
        assert result["status"] == "active"
        assert result["observation_stop"] is False
        assert result["auto_finalize_done"] is False
        assert result["target_days"] == 60
        assert result["retention_mode"] == "normal"
        assert result["clean_shutdown_marker"] == ""
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_observation_reflects_stop_flag():
    conn = _fresh_conn()
    try:
        set_stop_flag(conn, True)
        r = _make_routes(conn)
        result = await r.observation()
        assert result["observation_stop"] is True
        assert result["status"] == "stopped"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_observation_reflects_completed():
    conn = _fresh_conn()
    try:
        update_state(
            conn,
            auto_finalize_done=1,
            observation_completed_ms=1234567,
        )
        r = _make_routes(conn)
        result = await r.observation()
        assert result["auto_finalize_done"] is True
        assert result["observation_completed_ms"] == 1234567
        assert result["status"] == "completed"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_observation_returns_all_20_fields():
    conn = _fresh_conn()
    try:
        r = _make_routes(conn)
        result = await r.observation()
        expected = {
            "status",
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
        assert set(result.keys()) == expected
    finally:
        conn.close()