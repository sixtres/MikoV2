"""
Chaos: 429 storm handling, per-symbol circuit half-open.
Y-261 global_consecutive_429, decay 60s, circuit half-open.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.execution.rest_gateway import (
    RestGateway,
    RestGatewayConfig,
    _RateLimited429,
)


def _make_gw():
    cfg = RestGatewayConfig(
        circuit_429_threshold=3,
        circuit_open_seconds=60.0,
    )
    bucket = MagicMock()
    bucket.acquire = AsyncMock(return_value=True)
    pacer = MagicMock()
    pacer.enqueue = AsyncMock(return_value=None)
    client = MagicMock()
    return RestGateway(cfg, bucket, pacer, client)


def test_threshold_opens_circuit():
    gw = _make_gw()
    for _ in range(2):
        gw.record_429("BTCUSDT")
    assert gw.is_circuit_open("BTCUSDT") is False

    gw.record_429("BTCUSDT")
    assert gw.is_circuit_open("BTCUSDT") is True


def test_success_resets_counter():
    gw = _make_gw()
    gw.record_429("BTCUSDT")
    gw.record_429("BTCUSDT")
    gw.record_success("BTCUSDT")
    assert gw._consecutive_429["BTCUSDT"] == 0
    assert gw.is_circuit_open("BTCUSDT") is False


def test_per_symbol_independent_circuit():
    gw = _make_gw()
    for _ in range(3):
        gw.record_429("BTCUSDT")
    assert gw.is_circuit_open("BTCUSDT") is True
    assert gw.is_circuit_open("ETHUSDT") is False


@pytest.mark.asyncio
async def test_circuit_open_blocks_acquire():
    gw = _make_gw()
    for _ in range(3):
        gw.record_429("BTCUSDT")
    ok = await gw.acquire("1.1.1.1", "BTCUSDT")
    assert ok is False


@pytest.mark.asyncio
async def test_half_open_after_decay(monkeypatch):
    gw = _make_gw()
    for _ in range(3):
        gw.record_429("BTCUSDT")

    # simulate 61 seconds passed by rewinding monotonic
    base = time.monotonic()
    monkeypatch.setattr(
        "src.execution.rest_gateway.time.monotonic",
        lambda: base + 61.0,
    )
    # first probe allowed (half-open)
    ok1 = await gw.acquire("1.1.1.1", "BTCUSDT")
    assert ok1 is True
    gw.release("1.1.1.1", "BTCUSDT")

    # second probe blocked (still half-open, only 1 allowed)
    ok2 = await gw.acquire("1.1.1.1", "BTCUSDT")
    assert ok2 is False


@pytest.mark.asyncio
async def test_half_open_probe_success_closes_circuit(monkeypatch):
    gw = _make_gw()
    for _ in range(3):
        gw.record_429("BTCUSDT")

    base = time.monotonic()
    monkeypatch.setattr(
        "src.execution.rest_gateway.time.monotonic",
        lambda: base + 61.0,
    )
    # half-open probe allowed
    ok = await gw.acquire("1.1.1.1", "BTCUSDT")
    assert ok is True
    gw.release("1.1.1.1", "BTCUSDT")
    # success closes circuit
    gw.record_success("BTCUSDT")
    assert gw.is_circuit_open("BTCUSDT") is False


def test_storm_threshold_stable_after_open():
    """Repeated 429s after circuit open do not raise errors."""
    gw = _make_gw()
    for _ in range(20):
        gw.record_429("BTCUSDT")
    assert gw.is_circuit_open("BTCUSDT") is True
    assert gw._consecutive_429["BTCUSDT"] == 20


def test_multiple_symbols_storm():
    gw = _make_gw()
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        for _ in range(3):
            gw.record_429(sym)
    assert gw.is_circuit_open("BTCUSDT") is True
    assert gw.is_circuit_open("ETHUSDT") is True
    assert gw.is_circuit_open("SOLUSDT") is True


def test_config_defaults():
    cfg = RestGatewayConfig()
    assert cfg.circuit_429_threshold == 3
    assert cfg.circuit_open_seconds == 60.0
    assert cfg.circuit_half_open_test_max == 1


def test_no_global_state():
    assert not hasattr(RestGateway, "_consecutive_429")
    assert not hasattr(RestGateway, "_circuit_open_until")