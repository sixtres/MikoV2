import asyncio

import pytest

from src.dashboard.app import DashboardApp, DashboardConfig


def _make_app():
    cfg = DashboardConfig()
    routes = object()
    sqlite = object()
    lock = asyncio.Lock()
    return DashboardApp(cfg, routes, sqlite, lock), cfg


def test_config_defaults():
    cfg = DashboardConfig()
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8080
    assert cfg.static_cache_max_age == 31536000
    assert cfg.inline_css is True


@pytest.mark.asyncio
async def test_start_idempotent():
    app, _ = _make_app()
    await app.start()
    await app.start()
    assert app._started is True


@pytest.mark.asyncio
async def test_stop():
    app, _ = _make_app()
    await app.start()
    await app.stop()
    assert app._started is False


def test_get_app_returns_routes():
    app, _ = _make_app()
    assert app.get_app() is app._routes


def test_no_global_state():
    assert not hasattr(DashboardApp, "_started")