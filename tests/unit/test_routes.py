import asyncio

import pytest

from src.dashboard.routes import DashboardRoutes, RoutesConfig, SseEvent


def _make_routes(auth_token=""):
    cfg = RoutesConfig(auth_token=auth_token)
    lock = asyncio.Lock()
    return DashboardRoutes(cfg, lock), cfg


def test_config_defaults():
    cfg = RoutesConfig()
    assert cfg.auth_token == ""
    assert cfg.sse_throttle_normal_ms == 1000
    assert cfg.sse_throttle_emergency_ms == 100
    assert cfg.replay_buffer_size == 100
    assert cfg.alive_threshold_pct == 0.80


def test_validate_token_empty_config_allows_any():
    routes, _ = _make_routes()
    assert routes._validate_token("anything") is True


def test_validate_token_matching():
    routes, _ = _make_routes(auth_token="secret123")
    assert routes._validate_token("secret123") is True


def test_validate_token_mismatch():
    routes, _ = _make_routes(auth_token="secret123")
    assert routes._validate_token("wrong") is False


def test_replay_events_empty_buffer():
    routes, _ = _make_routes()
    assert routes._replay_events(0) == []


def test_replay_events_filter():
    routes, _ = _make_routes()
    routes._event_buffer = [
        SseEvent(event_id=1, data="a"),
        SseEvent(event_id=2, data="b"),
        SseEvent(event_id=3, data="c"),
    ]
    result = routes._replay_events(1)
    assert len(result) == 2
    assert result[0].event_id == 2
    assert result[1].event_id == 3


def test_replay_events_limit():
    cfg = RoutesConfig(replay_buffer_size=2)
    routes = DashboardRoutes(cfg, asyncio.Lock())
    routes._event_buffer = [
        SseEvent(event_id=i, data="x") for i in range(1, 6)
    ]
    result = routes._replay_events(0)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_sse_stream_auth_fail():
    routes, _ = _make_routes(auth_token="secret")
    with pytest.raises(PermissionError):
        async for _ in routes.sse_stream(None, "wrong"):
            pass


@pytest.mark.asyncio
async def test_sse_stream_yields_event():
    routes, _ = _make_routes()
    events = []
    async for ev in routes.sse_stream(None, "any"):
        events.append(ev)
    assert len(events) == 1
    assert isinstance(events[0], SseEvent)
    assert events[0].event_id == 1


@pytest.mark.asyncio
async def test_sse_stream_with_replay():
    routes, _ = _make_routes()
    routes._event_buffer = [
        SseEvent(event_id=1, data="a"),
        SseEvent(event_id=2, data="b"),
    ]
    events = []
    async for ev in routes.sse_stream(last_event_id=1, auth_token="any"):
        events.append(ev)
    assert len(events) == 2
    assert events[0].event_id == 2


@pytest.mark.asyncio
async def test_health_check_ok():
    routes, _ = _make_routes()
    status, body = await routes.health_check()
    assert status == 200
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_funding_status():
    routes, _ = _make_routes()
    result = await routes.funding_status()
    assert result["times"] == [0, 8, 16]
    assert "next" in result


def test_no_global_state():
    assert not hasattr(DashboardRoutes, "_event_buffer")
    assert not hasattr(DashboardRoutes, "_event_id_counter")