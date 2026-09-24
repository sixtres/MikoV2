import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dashboard.app import DashboardApp, DashboardConfig
from src.dashboard.routes import DashboardRoutes, RoutesConfig


def _make_app():
    cfg = DashboardConfig(host="127.0.0.1", port=0)
    routes_cfg = RoutesConfig()
    sqlite = MagicMock()
    sqlite.fetch = AsyncMock(return_value=[[0]])
    sqlite.list_open_positions = AsyncMock(return_value=[])
    sqlite.list_closed_positions = AsyncMock(return_value=[])
    sqlite.list_recent_whales = AsyncMock(return_value=[])
    sqlite.list_equity_snapshots = AsyncMock(return_value=[])
    sqlite.get_daily_stats = AsyncMock(return_value=None)
    lock = asyncio.Lock()
    routes = DashboardRoutes(routes_cfg, sqlite, lock)
    app = DashboardApp(cfg, routes, sqlite, lock)
    return app, cfg


def test_config_defaults():
    cfg = DashboardConfig()
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 10001
    assert cfg.static_cache_max_age == 31536000


@pytest.mark.asyncio
async def test_start_idempotent():
    app, _ = _make_app()
    await app.start()
    await app.start()
    assert app._started is True
    await app.stop()


@pytest.mark.asyncio
async def test_stop_after_start():
    app, _ = _make_app()
    await app.start()
    await app.stop()
    assert app._started is False


@pytest.mark.asyncio
async def test_get_app_returns_application():
    app, _ = _make_app()
    await app.start()
    assert app.get_app() is not None
    await app.stop()


@pytest.mark.asyncio
async def test_start_stop_twice_safe():
    app, _ = _make_app()
    await app.stop()  # before start, no-op
    await app.start()
    await app.stop()
    await app.stop()  # after stop, no-op


def test_no_global_state():
    assert not hasattr(DashboardApp, "_app")
    assert not hasattr(DashboardApp, "_runner")