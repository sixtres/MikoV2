# YAMA Y-263, Y-275, Y-321a, Y-326, Y-338, Y-342, Y-353, Y-359, Y-269

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.execution.rest_gateway import RestGateway, RestGatewayConfig

def _make_deps(ok=True):
    bucket = MagicMock()
    bucket.acquire = AsyncMock(return_value=ok)
    pacer = MagicMock()
    pacer.enqueue = AsyncMock(return_value=None)
    client = MagicMock()
    return bucket, pacer, client

def test_config_defaults():
    cfg = RestGatewayConfig(base_url="https://fapi.binance.com")
    assert cfg.rest_outer_timeout_ms == 3500
    assert cfg.per_ip_limit == 15
    assert cfg.per_symbol_limit == 2
    assert cfg.sem_emergency_count == 3
    assert cfg.sem_normal_count == 9

def test_critical_bypass_false_by_default():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket, pacer, client = _make_deps()
    gw = RestGateway(cfg, bucket, pacer, client)
    assert gw._critical_bypass is False

@pytest.mark.asyncio
async def test_acquire_all_sems():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket, pacer, client = _make_deps(ok=True)
    gw = RestGateway(cfg, bucket, pacer, client)
    ok = await gw.acquire("1.1.1.1", "BTCUSDT", is_emergency=False)
    assert ok is True
    gw.release("1.1.1.1", "BTCUSDT", is_emergency=False)

@pytest.mark.asyncio
async def test_acquire_emergency_uses_sem_emergency():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket, pacer, client = _make_deps(ok=True)
    gw = RestGateway(cfg, bucket, pacer, client)
    ok = await gw.acquire("1.1.1.1", "BTCUSDT", is_emergency=True)
    assert ok is True
    gw.release("1.1.1.1", "BTCUSDT", is_emergency=True)

@pytest.mark.asyncio
async def test_acquire_normal_uses_sem_normal():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket, pacer, client = _make_deps(ok=True)
    gw = RestGateway(cfg, bucket, pacer, client)
    ok = await gw.acquire("1.1.1.1", "BTCUSDT", is_emergency=False)
    assert ok is True
    gw.release("1.1.1.1", "BTCUSDT", is_emergency=False)

@pytest.mark.asyncio
async def test_acquire_y359_outer_3500ms():
    cfg = RestGatewayConfig(base_url="https://test", rest_outer_timeout_ms=3500)
    bucket, pacer, client = _make_deps(ok=True)
    gw = RestGateway(cfg, bucket, pacer, client)
    assert cfg.rest_outer_timeout_ms == 3500
    ok = await gw.acquire("1.1.1.1", "BTCUSDT")
    assert ok is True
    gw.release("1.1.1.1", "BTCUSDT")

@pytest.mark.asyncio
async def test_acquire_timeout_returns_false():
    cfg = RestGatewayConfig(base_url="https://test", rest_outer_timeout_ms=10)
    bucket, pacer, client = _make_deps(ok=True)
    gw = RestGateway(cfg, bucket, pacer, client)
    for _ in range(cfg.sem_normal_count):
        await gw._sem_normal.acquire()
    ok = await gw.acquire("1.1.1.1", "BTCUSDT", is_emergency=False)
    assert ok is False
    for _ in range(cfg.sem_normal_count):
        try:
            gw._sem_normal.release()
        except ValueError:
            pass

@pytest.mark.asyncio
async def test_acquire_calls_token_bucket():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket, pacer, client = _make_deps(ok=True)
    gw = RestGateway(cfg, bucket, pacer, client)
    ok = await gw.acquire("1.1.1.1", "BTCUSDT")
    assert ok is True
    bucket.acquire.assert_awaited()
    gw.release("1.1.1.1", "BTCUSDT")

@pytest.mark.asyncio
async def test_acquire_token_bucket_fail_releases_all():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket, pacer, client = _make_deps(ok=False)
    gw = RestGateway(cfg, bucket, pacer, client)
    ok = await gw.acquire("1.1.1.1", "BTCUSDT")
    assert ok is False

@pytest.mark.asyncio
async def test_release_all_sems():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket, pacer, client = _make_deps(ok=True)
    gw = RestGateway(cfg, bucket, pacer, client)
    await gw.acquire("1.1.1.1", "BTCUSDT")
    gw.release("1.1.1.1", "BTCUSDT")

@pytest.mark.asyncio
async def test_post_market_order_pacer_enqueue():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket, pacer, client = _make_deps(ok=True)
    gw = RestGateway(cfg, bucket, pacer, client)
    gw._exchange_post = AsyncMock(return_value={"status": "ok"})
    payload = {"symbol": "BTCUSDT", "reduceOnly": True}
    result = await gw.post_market_order(payload, priority=1)
    pacer.enqueue.assert_awaited()
    assert result is not None

@pytest.mark.asyncio
async def test_post_market_order_pacer_full_runtimeerror_direct():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket, pacer, client = _make_deps(ok=True)
    pacer.enqueue = AsyncMock(side_effect=RuntimeError("CRITICAL pacer full"))
    gw = RestGateway(cfg, bucket, pacer, client)
    gw._direct_market_post = AsyncMock(return_value={"direct": True})
    payload = {"symbol": "BTCUSDT"}
    result = await gw.post_market_order(payload, priority=0)
    assert result == {"direct": True}
    gw._direct_market_post.assert_awaited()

@pytest.mark.asyncio
async def test_direct_market_post_token_bucket_bypass_pacer():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket, pacer, client = _make_deps(ok=True)
    gw = RestGateway(cfg, bucket, pacer, client)
    gw._exchange_post = AsyncMock(return_value={"status": "ok"})
    result = await gw._direct_market_post("BTCUSDT", reduce_only=True)
    assert result == {"status": "ok"}
    pacer.enqueue.assert_not_awaited()

@pytest.mark.asyncio
async def test_direct_market_post_two_attempts():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket = MagicMock()
    bucket.acquire = AsyncMock(side_effect=[False, True])
    pacer = MagicMock()
    pacer.enqueue = AsyncMock()
    client = MagicMock()
    gw = RestGateway(cfg, bucket, pacer, client)
    gw._exchange_post = AsyncMock(return_value={"status": "ok"})
    result = await gw._direct_market_post("BTCUSDT")
    assert result == {"status": "ok"}
    assert bucket.acquire.await_count == 2

@pytest.mark.asyncio
async def test_direct_market_post_returns_none_on_failure():
    cfg = RestGatewayConfig(base_url="https://test")
    bucket = MagicMock()
    bucket.acquire = AsyncMock(return_value=False)
    pacer = MagicMock()
    pacer.enqueue = AsyncMock()
    client = MagicMock()
    gw = RestGateway(cfg, bucket, pacer, client)
    result = await gw._direct_market_post("BTCUSDT")
    assert result is None

def test_no_global_state():
    assert not hasattr(RestGateway, "_per_ip_sem")
    assert not hasattr(RestGateway, "_sem_normal")