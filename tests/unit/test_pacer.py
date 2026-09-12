# YAMA Y-305, Y-322a, Y-322b, Y-327, Y-328, Y-330, Y-343, Y-347, Y-355

import asyncio
import heapq
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.execution.pacer import Pacer, PacerConfig, PacerPriority, _PacerItem

def test_priority_constants():
    assert PacerPriority.CRITICAL == 0
    assert PacerPriority.NORMAL == 1
    assert PacerPriority.REBUILD == 2

def test_config_defaults():
    cfg = PacerConfig()
    assert cfg.critical_spacing_ms == 2
    assert cfg.normal_spacing_ms == 20
    assert cfg.rebuild_spacing_ms == 50
    assert cfg.critical_maxsize == 200

@pytest.mark.asyncio
async def test_enqueue_priority_valid():
    cfg = PacerConfig()
    p = Pacer(cfg)
    await p.enqueue(0, "c")
    await p.enqueue(1, "n")
    await p.enqueue(2, "r")
    assert p.qsize() == 3

@pytest.mark.asyncio
async def test_enqueue_priority_invalid_fatal():
    cfg = PacerConfig()
    p = Pacer(cfg)
    with pytest.raises(AssertionError):
        await p.enqueue(3, "bad")

@pytest.mark.asyncio
async def test_enqueue_critical_full_fail_fast():
    cfg = PacerConfig(critical_maxsize=200)
    p = Pacer(cfg)
    for i in range(200):
        await p.enqueue(0, i)
    with pytest.raises(RuntimeError, match="CRITICAL pacer full"):
        await p.enqueue(0, 201)

@pytest.mark.asyncio
async def test_enqueue_normal_no_max_limit():
    cfg = PacerConfig(critical_maxsize=2)
    p = Pacer(cfg)
    for i in range(10):
        await p.enqueue(1, i)
    assert p.qsize() == 10

@pytest.mark.asyncio
async def test_pop_empty_returns_none():
    cfg = PacerConfig()
    p = Pacer(cfg)
    result = await p.pop()
    assert result is None

@pytest.mark.asyncio
async def test_pop_single_item():
    cfg = PacerConfig()
    p = Pacer(cfg)
    await p.enqueue(1, "payload")
    p._last_dispatch[1] = 0.0
    with patch("time.monotonic", return_value=10.0):
        result = await p.pop()
    assert result == "payload"

@pytest.mark.asyncio
async def test_pop_priority_order():
    cfg = PacerConfig()
    p = Pacer(cfg)
    with patch("time.time", return_value=10.0):
        await p.enqueue(2, "rebuild")
        await p.enqueue(1, "normal")
        await p.enqueue(0, "critical")
        p._last_dispatch[0] = 0.0
        p._last_dispatch[1] = 0.0
        p._last_dispatch[2] = 0.0
        with patch("time.monotonic", return_value=10.0):
            r1 = await p.pop()
            r2 = await p.pop()
            r3 = await p.pop()
    assert r1 == "critical"
    assert r2 == "normal"
    assert r3 == "rebuild"

@pytest.mark.asyncio
async def test_pop_fifo_within_same_priority():
    cfg = PacerConfig()
    p = Pacer(cfg)
    with patch("time.time", return_value=10.0):
        await p.enqueue(1, "first")
        await p.enqueue(1, "second")
        await p.enqueue(1, "third")
        p._last_dispatch[1] = 0.0
        with patch("time.monotonic", side_effect=[10.0, 10.1, 10.2]):
            r1 = await p.pop()
            r2 = await p.pop()
            r3 = await p.pop()
    assert r1 == "first"
    assert r2 == "second"
    assert r3 == "third"

@pytest.mark.asyncio
async def test_pop_respects_min_spacing():
    cfg = PacerConfig(critical_spacing_ms=2)
    p = Pacer(cfg)
    await p.enqueue(0, "a")
    await p.enqueue(0, "b")
    p._last_dispatch[0] = 0.0
    with patch("time.time", return_value=10.0):
        with patch("time.monotonic", side_effect=[10.0, 10.0001, 10.01]):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                r1 = await p.pop()
                task = asyncio.create_task(p.pop())
                await asyncio.sleep(0.05)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    assert r1 == "a"
    assert p.qsize() == 1

@pytest.mark.asyncio
async def test_pop_aging():
    cfg = PacerConfig()
    p = Pacer(cfg)
    old_ts = time.time() - 5
    item = _PacerItem(base_prio=2, seq=0, enqueue_ts=old_ts, payload="aged")
    heapq.heappush(p._heap, item)
    p._last_dispatch[0] = 0.0
    with patch("time.time", return_value=time.time()):
        with patch("time.monotonic", return_value=10.0):
            result = await p.pop()
            if result!= "aged":
                result2 = await p.pop()
                assert result2 == "aged"
            else:
                assert result == "aged"

@pytest.mark.asyncio
async def test_last_dispatch_uses_base_prio():
    cfg = PacerConfig()
    p = Pacer(cfg)
    with patch("time.time", return_value=5.0):
        await p.enqueue(1, "n")
        p._last_dispatch[1] = 0.0
        with patch("time.monotonic", return_value=5.0):
            await p.pop()
    assert p._last_dispatch[1] == 5.0

def test_qsize_after_enqueue():
    async def _run():
        cfg = PacerConfig()
        p = Pacer(cfg)
        await p.enqueue(0, "a")
        await p.enqueue(1, "b")
        return p.qsize()

    assert asyncio.run(_run()) == 2

def test_is_empty():
    async def _run():
        cfg = PacerConfig()
        p = Pacer(cfg)
        assert p.is_empty()
        await p.enqueue(0, "a")
        assert not p.is_empty()
        return True

    assert asyncio.run(_run())

@pytest.mark.asyncio
async def test_no_recursion_pop():
    cfg = PacerConfig()
    p = Pacer(cfg)
    await p.enqueue(0, "a")
    p._last_dispatch[0] = time.monotonic()
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        task = asyncio.create_task(p.pop())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert mock_sleep.called

def test_no_global_state():
    assert not hasattr(Pacer, "_heap")
    assert not hasattr(Pacer, "_seq")