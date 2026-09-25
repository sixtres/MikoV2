# tests/unit/test_b3_5_inert_mode.py
"""B3.5-AC=A inert mode testleri.

Kapsam (STORM kilidi + PO eklentisi):
- Q1=A: transition emit noktasi runner _poll_observation_stop.
- Q2=B: OBSERVATION_STOPPED/RESUMED = WARNING (simetri).
- Q3=A: auth sonrasi GET-only middleware.
- Q4=B: last_transition_reason persistence + startup skip.
- GLM kaygi #3: inert modda /health 200 + status=observation_stopped.
"""
from __future__ import annotations

import asyncio
import sqlite3
from unittest.mock import AsyncMock, MagicMock

from aiohttp import web

from src.alerting.event_catalog import (
    SEVERITY_WARNING,
    get_severity,
)
from src.dashboard.app import DashboardApp, DashboardConfig
from src.dashboard.routes import DashboardRoutes, RoutesConfig
from src.observation.migration import migrate_observation
from src.observation.state import load_state, set_stop_flag


# --- Q2=B: event catalog ---


def test_event_catalog_stop_resume_are_warning():
    assert get_severity("OBSERVATION_STOPPED") == SEVERITY_WARNING
    assert get_severity("OBSERVATION_RESUMED") == SEVERITY_WARNING


# --- Q3=A: middleware ---


class _FakeSqliteWriter:
    async def fetch(self, *a, **kw):
        return [(0,)]


def _make_app(tmp_path, stop: bool = False):
    conn = sqlite3.connect(str(tmp_path / "t.sqlite"))
    migrate_observation(conn)
    if stop:
        set_stop_flag(conn, True)
    lock = asyncio.Lock()
    routes = DashboardRoutes(
        RoutesConfig(),
        _FakeSqliteWriter(),
        lock,
        conn=conn,
    )
    app = DashboardApp(
        DashboardConfig(),
        routes,
        _FakeSqliteWriter(),
        lock,
    )
    return app, routes, conn


def _fake_request(method: str, path: str, auth: str = "") -> MagicMock:
    req = MagicMock()
    req.path = path
    req.method = method
    req.headers = {"Authorization": auth} if auth else {}
    req.query = {}
    return req


def test_middleware_blocks_post_when_stopped(tmp_path):
    app, routes, conn = _make_app(tmp_path, stop=True)
    handler = AsyncMock(return_value=web.Response(text="ok"))
    req = _fake_request("POST", "/api/v2/alert_test", auth="Bearer ")
    resp = asyncio.run(app._auth_middleware(req, handler))
    assert resp.status == 503
    handler.assert_not_called()
    conn.close()


def test_middleware_allows_get_when_stopped(tmp_path):
    app, routes, conn = _make_app(tmp_path, stop=True)
    handler = AsyncMock(return_value=web.Response(text="ok"))
    req = _fake_request("GET", "/api/v2/observation", auth="Bearer ")
    resp = asyncio.run(app._auth_middleware(req, handler))
    assert resp.status == 200
    handler.assert_called_once()
    conn.close()


def test_middleware_allows_post_when_not_stopped(tmp_path):
    app, routes, conn = _make_app(tmp_path, stop=False)
    handler = AsyncMock(return_value=web.Response(text="ok"))
    req = _fake_request("POST", "/api/v2/alert_test", auth="Bearer ")
    resp = asyncio.run(app._auth_middleware(req, handler))
    assert resp.status == 200
    handler.assert_called_once()
    conn.close()


def test_middleware_auth_before_inert(tmp_path):
    """Token yoksa 401; token varsa inert 503 (GLM sandbox emsali)."""
    app, routes, conn = _make_app(tmp_path, stop=True)
    routes._config = RoutesConfig(auth_token="secret")
    handler = AsyncMock(return_value=web.Response(text="ok"))
    # Auth once: token yok -> 401
    req = _fake_request("POST", "/api/v2/alert_test", auth="")
    resp = asyncio.run(app._auth_middleware(req, handler))
    assert resp.status == 401
    handler.assert_not_called()
    # Auth gecti, inert blokladi -> 503
    req2 = _fake_request("POST", "/api/v2/alert_test", auth="Bearer secret")
    resp2 = asyncio.run(app._auth_middleware(req2, handler))
    assert resp2.status == 503
    conn.close()


# --- health (GLM kaygi #3) ---


def test_health_returns_observation_stopped(tmp_path):
    app, routes, conn = _make_app(tmp_path, stop=True)
    status, body = asyncio.run(routes.health())
    assert status == 200
    assert body["status"] == "observation_stopped"
    conn.close()


def test_health_returns_ok_when_active(tmp_path):
    app, routes, conn = _make_app(tmp_path, stop=False)
    status, body = asyncio.run(routes.health())
    assert status == 200
    assert body["status"] == "ok"
    conn.close()


# --- Q1+Q4: runner transition emit + startup skip ---


class _FakeAlert:
    def __init__(self) -> None:
        self.emits: list[tuple[str, dict]] = []

    async def emit(self, event_type: str, payload: dict) -> None:
        self.emits.append((event_type, payload))


class _FakePaper:
    async def on_entry(self, **kw):
        pass

    def get_open_position_qty(self, symbol: str) -> float:
        return 0.0


def _make_runner(tmp_path):
    from tests.shadow.runner import ShadowRunner

    runner = ShadowRunner(
        symbols=["BTC_USDT"],
        duration_s=0,
        db_path=tmp_path / "r.sqlite",
    )
    runner._setup_db()
    runner._alert_agent = _FakeAlert()
    runner._paper = _FakePaper()
    return runner


def test_runner_transition_emits_once_and_persists(tmp_path):
    runner = _make_runner(tmp_path)
    runner._observation_stopped = False
    set_stop_flag(runner._conn, True)
    asyncio.run(runner._poll_observation_stop())
    assert len(runner._alert_agent.emits) == 1
    assert runner._alert_agent.emits[0][0] == "OBSERVATION_STOPPED"
    st = load_state(runner._conn)
    assert st.last_transition_reason == "OBSERVATION_STOPPED"
    # Ikinci poll: transition yok, emit yok (Q1=A)
    asyncio.run(runner._poll_observation_stop())
    assert len(runner._alert_agent.emits) == 1
    runner._conn.close()


def test_runner_transition_resume_emits(tmp_path):
    runner = _make_runner(tmp_path)
    runner._observation_stopped = True
    set_stop_flag(runner._conn, False)
    asyncio.run(runner._poll_observation_stop())
    assert len(runner._alert_agent.emits) == 1
    assert runner._alert_agent.emits[0][0] == "OBSERVATION_RESUMED"
    st = load_state(runner._conn)
    assert st.last_transition_reason == "OBSERVATION_RESUMED"
    runner._conn.close()


def test_runner_startup_sync_suppresses_reemit(tmp_path):
    """Flag True iken restart, in-memory True olur, emit yok (Q4=B)."""
    runner = _make_runner(tmp_path)
    set_stop_flag(runner._conn, True)
    # run() icindeki startup sync'i simule et
    st = load_state(runner._conn)
    runner._observation_stopped = bool(st.observation_stop)
    assert runner._observation_stopped is True
    asyncio.run(runner._poll_observation_stop())
    assert len(runner._alert_agent.emits) == 0
    runner._conn.close()