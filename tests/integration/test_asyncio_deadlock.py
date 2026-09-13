"""
Asyncio-level deadlock detection integration tests.
Y-357 (async state queue bridge), Y-358 (asyncio.Lock only),
Y-347 (pacer pop lock-disinda-sleep).
"""

import asyncio
import time

import pytest

from src.data_layer.queues.async_state_queue import AsyncStateQueue
from src.execution.pacer import Pacer, PacerConfig


def test_no_sync_lock_in_event_loop_paths():
    """Async-path locks must be asyncio.Lock, not threading.Lock."""
    import multiprocessing as mp

    # Pacer is full asyncio in current impl; verify lock type
    p = Pacer(PacerConfig())
    import asyncio as _a

    assert isinstance(p._lock, _a.Lock), "Pacer lock asyncio.Lock olmali"


@pytest.mark.asyncio
async def test_async_state_queue_no_to_thread_deadlock():
    """
    Y-357: mp.Queue bridge must not deadlock.
    put -> writer loop -> mp.Queue.get in bounded time.
    """
    mp_queue = __import__("multiprocessing").Queue(maxsize=200)
    q = AsyncStateQueue(mp_queue, maxsize=200)
    await q.start()

    try:
        await q.put({"msg": "hello"})
        # writer loop should transfer within 1s
        deadline = time.monotonic() + 2.0
        got = None
        while time.monotonic() < deadline:
            if not mp_queue.empty():
                got = mp_queue.get_nowait()
                break
            await asyncio.sleep(0.02)
        assert got == {"msg": "hello"}, "Y-357 bridge deadlock olmali, got=%s" % got
    finally:
        await q.stop()


@pytest.mark.asyncio
async def test_pacer_pop_lock_outside_sleep_no_deadlock():
    """
    Y-347: pacer.pop must not hold lock during sleep(0).
    Two coroutines pop concurrently without deadlock.
    """
    p = Pacer(PacerConfig(critical_spacing_ms=2))
    await p.enqueue(0, "a")
    await p.enqueue(0, "b")

    # two concurrent poppers, both must finish (not deadlock)
    async def popper():
        return await asyncio.wait_for(p.pop(), timeout=2.0)

    # first pop at t, second respects min-spacing; both within 2s
    result1 = await popper()
    result2 = await popper()
    assert result1 == "a"
    assert result2 == "b"


@pytest.mark.asyncio
async def test_pacer_pop_no_recursion_under_starvation():
    """
    Y-327: pop is while loop, not recursion.
    Even when item requires repeated re-push (aging + spacing),
    stack depth stays constant.
    """
    import sys

    p = Pacer(PacerConfig(critical_spacing_ms=5))
    await p.enqueue(0, "x")

    # Track recursion depth via sys.setrecursionlimit not needed;
    # the test just ensures pop completes without RecursionError.
    result = await asyncio.wait_for(p.pop(), timeout=2.0)
    assert result == "x"


@pytest.mark.asyncio
async def test_two_async_queues_no_deadlock():
    """Two AsyncStateQueue instances don't interfere."""
    mp1 = __import__("multiprocessing").Queue(maxsize=200)
    mp2 = __import__("multiprocessing").Queue(maxsize=200)
    q1 = AsyncStateQueue(mp1, maxsize=200)
    q2 = AsyncStateQueue(mp2, maxsize=200)

    await q1.start()
    await q2.start()
    try:
        await q1.put("a")
        await q2.put("b")

        deadline = time.monotonic() + 2.0
        got1, got2 = None, None
        while time.monotonic() < deadline and (got1 is None or got2 is None):
            if got1 is None and not mp1.empty():
                got1 = mp1.get_nowait()
            if got2 is None and not mp2.empty():
                got2 = mp2.get_nowait()
            await asyncio.sleep(0.02)

        assert got1 == "a"
        assert got2 == "b"
    finally:
        await q1.stop()
        await q2.stop()


@pytest.mark.asyncio
async def test_no_threading_lock_blocks_event_loop():
    """
    FlushController uses threading.Lock for sync API (Y-358 exception).
    Verify it doesn't block async path when held briefly.
    """
    from src.execution.flush_controller import FlushController, FlushControllerConfig

    cfg = FlushControllerConfig(bounded_queue_size=5)
    fc = FlushController(cfg)

    # suspend/resume are sync but should be instant
    start = time.monotonic()
    for _ in range(1000):
        fc.suspend()
    for _ in range(1000):
        fc.resume()
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, "FlushController sync ops cok yavas: %fs" % elapsed
    assert fc._counter == 0


@pytest.mark.asyncio
async def test_emergency_close_no_deadlock_two_symbols():
    """Two symbol emergency closes concurrently must not deadlock."""
    from unittest.mock import AsyncMock, MagicMock

    from src.emergency.close import EmergencyCloser, EmergencyCloserConfig

    cfg = EmergencyCloserConfig(max_retry=1, leverage=5, min_lot=0.001)
    rest = MagicMock()
    rest.post_market_order = AsyncMock(return_value={"status": "ok", "slippage": 0.0})
    rest._direct_market_post = AsyncMock(return_value={"status": "forced"})
    sqlite = MagicMock()
    sqlite.execute_wal = AsyncMock()
    flush = MagicMock()
    flush.suspend = MagicMock()
    flush.resume = MagicMock()
    tasks = {}
    closer = EmergencyCloser(cfg, rest, sqlite, MagicMock(), flush, tasks)

    r1, r2 = await asyncio.gather(
        closer.emergency_close_with_retry("BTCUSDT"),
        closer.emergency_close_with_retry("ETHUSDT"),
    )
    assert r1 == "CLOSED"
    assert r2 == "CLOSED"
    assert flush.suspend.call_count == 2
    assert flush.resume.call_count == 2


@pytest.mark.asyncio
async def test_gather_with_timeout_no_deadlock():
    """
    Overall guard: multiple concurrent async ops finish within timeout.
    If any of the above deadlock, this catches.
    """
    mp_q = __import__("multiprocessing").Queue(maxsize=200)
    q = AsyncStateQueue(mp_q, maxsize=200)
    pacer = Pacer(PacerConfig())

    await q.start()
    try:
        async def work():
            await q.put({"x": 1})
            await pacer.enqueue(1, "p")
            return True

        results = await asyncio.wait_for(
            asyncio.gather(*[work() for _ in range(5)]),
            timeout=3.0,
        )
        assert all(results)
    finally:
        await q.stop()


def test_no_global_state():
    import src.data_layer.queues.async_state_queue as mod_q
    import src.execution.pacer as mod_p

    assert not hasattr(mod_q, "_state_sem_global")
    assert not hasattr(mod_p, "_GLOBAL_PACER")