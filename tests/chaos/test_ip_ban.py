"""
Chaos: per-IP ban simulation + 429 circuit interaction.
Y-261 global 429 per-symbol, Y-321a IP->symbol order.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.execution.rest_gateway import RestGateway, RestGatewayConfig


def _mk_gw(threshold=3):
    cfg = RestGatewayConfig(
        circuit_429_threshold=threshold,
        circuit_open_seconds=60.0,
        per_ip_limit=2,
        per_symbol_limit=1,
    )
    bucket = MagicMock()
    bucket.acquire = AsyncMock(return_value=True)
    pacer = MagicMock()
    pacer.enqueue = AsyncMock(return_value=None)
    return RestGateway(cfg, bucket, pacer, MagicMock())


@pytest.mark.asyncio
async def test_ip_semaphore_limits_concurrent():
    """Per-IP limit: same IP, different symbols."""
    gw = _mk_gw()  # per_ip_limit=2, per_symbol_limit=1
    # fill per-ip with different symbols
    assert await gw.acquire("1.1.1.1", "BTC_USDT") is True
    assert await gw.acquire("1.1.1.1", "ETH_USDT") is True
    # 3rd symbol on same IP -> IP limit hit
    ok = await gw.acquire("1.1.1.1", "SOL_USDT")
    assert ok is False
    gw.release("1.1.1.1", "BTC_USDT")
    gw.release("1.1.1.1", "ETH_USDT")


@pytest.mark.asyncio
async def test_different_ips_independent():
    """Different IPs on different symbols both succeed."""
    gw = _mk_gw()
    assert await gw.acquire("1.1.1.1", "BTC_USDT") is True
    assert await gw.acquire("2.2.2.2", "ETH_USDT") is True
    gw.release("1.1.1.1", "BTC_USDT")
    gw.release("2.2.2.2", "ETH_USDT")


def test_ip_ban_circuit_per_symbol_independent():
    """Circuit breaker for BTC_USDT does not affect ETH_USDT."""
    gw = _mk_gw(threshold=3)
    for _ in range(3):
        gw.record_429("BTC_USDT")
    assert gw.is_circuit_open("BTC_USDT") is True
    assert gw.is_circuit_open("ETH_USDT") is False


@pytest.mark.asyncio
async def test_ip_banned_symbol_acquire_returns_false():
    gw = _mk_gw(threshold=2)
    for _ in range(2):
        gw.record_429("BTC_USDT")
    ok = await gw.acquire("1.1.1.1", "BTC_USDT")
    assert ok is False


def test_success_resets_429_counter():
    gw = _mk_gw(threshold=3)
    gw.record_429("BTC_USDT")
    gw.record_429("BTC_USDT")
    gw.record_success("BTC_USDT")
    assert gw._consecutive_429["BTC_USDT"] == 0


def test_multiple_symbols_storm_circuit_opens_independently():
    gw = _mk_gw(threshold=3)
    for sym in ("BTC_USDT", "ETH_USDT", "SOL_USDT"):
        for _ in range(3):
            gw.record_429(sym)
    assert gw.is_circuit_open("BTC_USDT") is True
    assert gw.is_circuit_open("ETH_USDT") is True
    assert gw.is_circuit_open("SOL_USDT") is True


def test_no_global_state():
    assert not hasattr(RestGateway, "_consecutive_429")