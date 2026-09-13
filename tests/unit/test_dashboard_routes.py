import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dashboard.routes import DashboardRoutes, RoutesConfig


def _make_routes(**cfg_over):
    cfg = RoutesConfig(**cfg_over)
    sqlite = MagicMock()
    sqlite.fetch = AsyncMock(return_value=[[0]])
    sqlite.list_open_positions = AsyncMock(return_value=[])
    sqlite.list_closed_positions = AsyncMock(return_value=[])
    sqlite.list_recent_whales = AsyncMock(return_value=[])
    sqlite.list_equity_snapshots = AsyncMock(return_value=[])
    sqlite.get_daily_stats = AsyncMock(return_value=None)
    lock = asyncio.Lock()
    return DashboardRoutes(cfg, sqlite, lock), sqlite, cfg


def test_config_defaults():
    cfg = RoutesConfig()
    assert cfg.auth_token == ""
    assert cfg.sse_throttle_normal_ms == 1000
    assert cfg.replay_buffer_size == 100


def test_validate_token_empty_config_allows_any():
    r, _, _ = _make_routes()
    assert r.validate_token("anything") is True


def test_validate_token_matching_and_mismatch():
    r, _, _ = _make_routes(auth_token="secret")
    assert r.validate_token("secret") is True
    assert r.validate_token("wrong") is False


@pytest.mark.asyncio
async def test_health_ok():
    r, _, _ = _make_routes()
    status, body = await r.health()
    assert status == 200
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_positions_empty():
    r, _, _ = _make_routes()
    result = await r.positions()
    assert result["open"] == []
    assert result["closed"] == []


@pytest.mark.asyncio
async def test_positions_maps_open_row():
    r, sqlite, _ = _make_routes()
    sqlite.list_open_positions = AsyncMock(
        return_value=[
            ("p1", "BTC_USDT", "LONG", 1000, 100.0, 0.5, 0.5,
             110.0, 95.0, 0, 0, 3, "IN_TOP5", 0, 0)
        ]
    )
    result = await r.positions()
    assert len(result["open"]) == 1
    assert result["open"][0]["position_id"] == "p1"
    assert result["open"][0]["symbol"] == "BTC_USDT"


@pytest.mark.asyncio
async def test_whales_empty():
    r, _, _ = _make_routes()
    result = await r.whales()
    assert result["whales"] == []


@pytest.mark.asyncio
async def test_equity_empty():
    r, _, _ = _make_routes()
    result = await r.equity()
    assert result["points"] == []
    assert result["latest"] is None


@pytest.mark.asyncio
async def test_pnl_no_data():
    r, _, _ = _make_routes()
    result = await r.pnl()
    assert result["today"] is None
    assert result["all_time"]["trades"] == 0
    assert result["all_time"]["win_rate"] == 0.0


@pytest.mark.asyncio
async def test_pnl_computes_win_rate():
    r, sqlite, _ = _make_routes()
    # closed rows: id, symbol, side, opened_at, closed_at, reason, avg,
    #              realized_pnl, fee, r_multiple
    sqlite.list_closed_positions = AsyncMock(
        return_value=[
            ("p1", "BTC_USDT", "LONG", 0, 0, "TP", 100.0, 10.0, 0.2, 2.0),
            ("p2", "BTC_USDT", "LONG", 0, 0, "SL", 100.0, -5.0, 0.1, -1.0),
            ("p3", "BTC_USDT", "SHORT", 0, 0, "TP", 100.0, 3.0, 0.1, 1.5),
        ]
    )
    result = await r.pnl()
    assert result["all_time"]["wins"] == 2
    assert result["all_time"]["losses"] == 1
    assert abs(result["all_time"]["win_rate"] - 2 / 3) < 1e-3


@pytest.mark.asyncio
async def test_metrics_returns_uptime():
    r, _, _ = _make_routes()
    result = await r.metrics()
    assert result["uptime_s"] >= 0


def test_push_event_and_replay():
    r, _, _ = _make_routes(replay_buffer_size=5)
    for i in range(10):
        r.push_event("test_event", {"i": i})
    # buffer trimmed to 5
    assert len(r._event_buffer) == 5
    # replay from id 5 returns last 5
    replayed = r._replay_events(5)
    assert len(replayed) == 5


@pytest.mark.asyncio
async def test_sse_stream_auth_fail():
    r, _, _ = _make_routes(auth_token="secret")
    gen = r.sse_stream(None, "wrong")
    with pytest.raises(PermissionError):
        await gen.__anext__()


@pytest.mark.asyncio
async def test_sse_stream_yields_keepalive():
    r, _, _ = _make_routes(sse_throttle_normal_ms=10)
    gen = r.sse_stream(None, "any")
    ev = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
    assert ev["event"] == "keepalive"
    await gen.aclose()


def test_no_global_state():
    assert not hasattr(DashboardRoutes, "_event_buffer")