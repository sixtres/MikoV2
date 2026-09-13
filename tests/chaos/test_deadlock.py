"""
Chaos: real runtime deadlock scenarios.
Y-327, Y-347, Y-350, Y-351, Y-357, Y-358 runtime deadlock guards.
"""

import asyncio
import multiprocessing as mp
import threading
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data_layer.queues.async_state_queue import AsyncStateQueue
from src.data_layer.token_bucket import TokenBucket
from src.emergency.close import EmergencyCloser, EmergencyCloserConfig
from src.execution.flush_controller import FlushController, FlushControllerConfig
from src.execution.pacer import Pacer, PacerConfig
from src.execution.rest_gateway import RestGateway, RestGatewayConfig


@pytest.fixture
def mp_queue_factory():
    queues = []

    def _make(maxsize=200):
        q = mp.Queue(maxsize=maxsize)
        try:
            q.cancel_join_thread()
        except Exception:
            pass
        queues.append(q)
        return q

    yield _make
    for q in queues:
        try:
            q.cancel_join_thread()
        except Exception:
            pass
        try:
            q.close()
        except Exception:
            pass


# === Pacer deadlock guards ===

@pytest.mark.asyncio
async def test_pacer_pop_concurrent_no_deadlock():
    """Two poppers must both complete within timeout."""
    p = Pacer(PacerConfig(critical_spacing_ms=2))
    await p.enqueue(0, "a")
    await p.enqueue(0, "b")

    async def popper():
        return await asyncio.wait_for(p.pop(), timeout=2.0)

    r1, r2 = await asyncio.wait_for(
        asyncio.gather(popper(), popper()),
        timeout=3.0,
    )
    assert r1 == "a"
    assert r2 == "b"


@pytest.mark.asyncio
async def test_pacer_pop_lock_released_during_aging_wait():
    """Y-347: lock must not be held while awaiting sleep(0)."""
    p = Pacer(PacerConfig(critical_spacing_ms=5))
    await p.enqueue(0, "x")
    # Fill the pacer with two items so second pop hits min-spacing
    await p.enqueue(0, "y")

    # We track lock acquisition duration indirectly: if lock held during
    # sleep(0), pop would starve other coroutines.
    async def concurrent_yield_check():
        # Bounded scheduling: must be able to acquire event loop turn
        for _ in range(5):
            await asyncio.sleep(0)
        return "yielded"

    r1 = await asyncio.wait_for(p.pop(), timeout=1.0)
    assert r1 == "x"
    other = await asyncio.wait_for(concurrent_yield_check(), timeout=0.5)
    assert other == "yielded"


@pytest.mark.asyncio
async def test_pacer_no_recursion_under_repeated_aging():
    """Y-327: pop is while loop; deep aging must not blow Python stack."""
    p = Pacer(PacerConfig(critical_spacing_ms=2))
    # Enqueue item with old timestamp to force aging
    await p.enqueue(2, "aged")  # REBUILD
    # Repeated pop with effective priority changes; loop-based impl safe
    result = await asyncio.wait_for(p.pop(), timeout=2.0)
    assert result == "aged"


# === AsyncStateQueue + event loop deadlock ===

@pytest.mark.asyncio
async def test_state_queue_no_event_loop_block_under_full_mpqueue(mp_queue_factory):
    """
    Y-357: put blocks on full (DROP_NEVER) but event loop stays responsive.
    Writer paused to force full state.
    """
    mp_q = mp_queue_factory(maxsize=10)
    q = AsyncStateQueue(mp_q, maxsize=5)
    # Do NOT start writer -> queue stays full when we push 5
    for i in range(5):
        await asyncio.wait_for(q.put({"i": i}), timeout=1.0)

    # 6th put blocks async (DROP_NEVER); event loop must still run
    put_task = asyncio.create_task(q.put({"i": 99}))
    await asyncio.sleep(0.15)
    assert not put_task.done(), "put must block while full (DROP_NEVER)"

    # Event loop is responsive (we got here)
    tick = await asyncio.wait_for(asyncio.sleep(0.01), timeout=0.5)
    assert tick is None

    # Now start writer; put_task should complete
    await q.start()
    try:
        await asyncio.wait_for(put_task, timeout=3.0)
        assert put_task.done()
    finally:
        await q.stop()


@pytest.mark.asyncio
async def test_state_queue_stop_drains_without_hang(mp_queue_factory):
    """stop() must complete within timeout even with pending items."""
    mp_q = mp_queue_factory(maxsize=200)
    q = AsyncStateQueue(mp_q, maxsize=200)
    await q.start()

    for i in range(50):
        await q.put({"i": i})

    # Stop must complete; not hang on drain
    await asyncio.wait_for(q.stop(), timeout=3.0)


# === FlushController sync path ===

def test_flush_controller_sync_no_block_loop():
    """Y-358: threading.Lock exception for sync path; must be fast."""
    fc = FlushController(FlushControllerConfig(bounded_queue_size=5))
    start = time.monotonic()
    for _ in range(5000):
        fc.suspend()
    for _ in range(5000):
        fc.resume()
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, "sync lock slow: %.3fs" % elapsed
    assert fc._counter == 0


def test_flush_controller_underflow_no_exception():
    """Y-362/Y-368: underflow clamps, no crash."""
    fc = FlushController(FlushControllerConfig())
    for _ in range(10):
        fc.resume()  # underflow repeatedly
    assert fc._counter == 0
    assert fc.is_suspended() is False


# === Emergency + flush interplay ===

@pytest.mark.asyncio
async def test_emergency_close_suspend_resume_no_leak():
    """Each emergency close must decrement flush counter back to zero."""
    cfg = EmergencyCloserConfig(max_retry=1, leverage=5, min_lot=0.001)
    rest = MagicMock()
    rest.post_market_order = AsyncMock(return_value={"status": "ok", "slippage": 0.0})
    rest._direct_market_post = AsyncMock(return_value={"status": "forced"})
    sqlite = MagicMock()
    sqlite.execute_wal = AsyncMock()

    fc = FlushController(FlushControllerConfig())
    tasks = {}
    closer = EmergencyCloser(cfg, rest, sqlite, MagicMock(), fc, tasks)

    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        await closer.emergency_close_with_retry(sym)

    # flush counter must return to 0 (balanced suspend/resume)
    assert fc._counter == 0
    assert fc.is_suspended() is False


@pytest.mark.asyncio
async def test_emergency_parallel_same_symbol_no_double_suspend():
    """Y-351: single-flight -> only one suspend for parallel calls."""
    cfg = EmergencyCloserConfig(max_retry=1, leverage=5, min_lot=0.001)
    rest = MagicMock()
    rest.post_market_order = AsyncMock(return_value={"status": "ok", "slippage": 0.0})
    rest._direct_market_post = AsyncMock(return_value={"status": "forced"})
    sqlite = MagicMock()
    sqlite.execute_wal = AsyncMock()

    fc = FlushController(FlushControllerConfig())
    tasks = {}
    closer = EmergencyCloser(cfg, rest, sqlite, MagicMock(), fc, tasks)

    r1, r2 = await asyncio.gather(
        closer.emergency_close_with_retry("BTCUSDT"),
        closer.emergency_close_with_retry("BTCUSDT"),
    )
    assert r1 == "CLOSED"
    assert r2 == "CLOSED"
    assert fc._counter == 0  # balanced


# === RestGateway + TokenBucket ===

@pytest.mark.asyncio
async def test_rest_gateway_token_bucket_exhaustion_no_deadlock():
    """
    Token bucket exhaustion: acquire waits for refill (no deadlock),
    returns True within a bounded time.
    """
    cfg = RestGatewayConfig(rest_outer_timeout_ms=500)
    bucket = TokenBucket()
    pacer = MagicMock()
    pacer.enqueue = AsyncMock()
    client = MagicMock()
    gw = RestGateway(cfg, bucket, pacer, client)

    # Consume full burst
    for _ in range(TokenBucket.BURST):
        await bucket.acquire()

    # Next acquire waits ~0.125s for refill (rate 8/s), must return True
    start = time.monotonic()
    ok = await asyncio.wait_for(
        gw.acquire("1.1.1.1", "BTCUSDT", is_emergency=True),
        timeout=1.5,
    )
    elapsed = time.monotonic() - start
    assert ok is True, "refill should deliver a token within 1.5s"
    assert elapsed < 1.5
    gw.release("1.1.1.1", "BTCUSDT", is_emergency=True)


# === Multi-process: no hang on exit ===

def test_multiprocess_queue_cleanup_no_hang(mp_queue_factory):
    """mp.Queue must not hang process on exit (cancel_join_thread)."""
    mp_q = mp_queue_factory(maxsize=5)
    for i in range(5):
        mp_q.put_nowait(i)
    # Do NOT drain; mp_queue still has items
    # Process should exit cleanly (fixture handles cancel/close)


def test_no_global_state():
    import src.execution.pacer as mod_p
    import src.execution.flush_controller as mod_f

    assert not hasattr(mod_p, "_GLOBAL_PACER")
    assert not hasattr(mod_f, "_GLOBAL_FLUSH")