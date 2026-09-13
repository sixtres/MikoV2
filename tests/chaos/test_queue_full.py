"""
Chaos: state_queue full behavior under burst load.
Y-276 DROP_NEVER state, DROP_OLDEST telemetry, Y-357 bridge no deadlock.
"""

import asyncio
import multiprocessing as mp
import threading
import time

import pytest

from src.data_layer.queues.async_state_queue import AsyncStateQueue
from src.data_layer.queues.async_telemetry_queue import AsyncTelemetryQueue


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


@pytest.mark.asyncio
async def test_state_queue_drop_never_blocks_when_full(mp_queue_factory):
    mp_q = mp_queue_factory(maxsize=200)
    q = AsyncStateQueue(mp_q, maxsize=200)
    for i in range(200):
        await q.put({"i": i})
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.put({"i": 200}), timeout=0.3)


@pytest.mark.asyncio
async def test_state_queue_writer_drains_and_unblocks(mp_queue_factory):
    mp_q = mp_queue_factory(maxsize=200)
    q = AsyncStateQueue(mp_q, maxsize=200)

    drained_items = []
    stop_flag = {"stop": False}

    def consumer():
        while not stop_flag["stop"]:
            try:
                item = mp_q.get(timeout=0.5)
                drained_items.append(item)
            except Exception:
                pass

    consumer_thread = threading.Thread(target=consumer, daemon=True)
    consumer_thread.start()

    await q.start()
    try:
        for i in range(250):
            await asyncio.wait_for(q.put({"i": i}), timeout=3)
        await asyncio.sleep(0.5)
        assert len(drained_items) >= 200
    finally:
        await q.stop()
        stop_flag["stop"] = True
        consumer_thread.join(timeout=2.0)


@pytest.mark.asyncio
async def test_telemetry_drop_oldest_under_burst():
    tq = AsyncTelemetryQueue(maxsize=1000, threaded_bridge=False)
    try:
        for i in range(1500):
            tq.put_nowait({"i": i})
        assert tq.dropped_count() >= 500
        first = tq.get_nowait()
        # oldest values are dropped, first surviving index > 0
        assert first["i"] > 0
    finally:
        tq.close()


@pytest.mark.asyncio
async def test_telemetry_put_nowait_never_blocks():
    tq = AsyncTelemetryQueue(maxsize=10, threaded_bridge=False)
    try:
        for i in range(100):
            tq.put_nowait({"i": i})
        assert tq.qsize() == 10
        assert tq.dropped_count() == 90
    finally:
        tq.close()


@pytest.mark.asyncio
async def test_state_queue_200_hard_limit(mp_queue_factory):
    mp_q = mp_queue_factory(maxsize=200)
    q = AsyncStateQueue(mp_q, maxsize=200)
    assert q.maxsize == 200
    for i in range(200):
        await q.put({"i": i})
    assert q.qsize_async() == 200


@pytest.mark.asyncio
async def test_queue_full_burst_no_deadlock(mp_queue_factory):
    mp_q = mp_queue_factory(maxsize=200)
    q = AsyncStateQueue(mp_q, maxsize=200)
    await q.start()
    try:
        async def producer(base):
            for i in range(50):
                await asyncio.wait_for(q.put({"base": base, "i": i}), timeout=5)

        await asyncio.wait_for(
            asyncio.gather(*[producer(b) for b in range(5)]),
            timeout=10.0,
        )
        await asyncio.sleep(0.5)
        drained = 0
        while not mp_q.empty():
            mp_q.get_nowait()
            drained += 1
        assert drained >= 200
    finally:
        await q.stop()


def test_telemetry_dropped_counter_increments():
    tq = AsyncTelemetryQueue(maxsize=5, threaded_bridge=False)
    try:
        for i in range(100):
            tq.put_nowait({"i": i})
        assert tq.dropped_count() == 95
        assert tq.qsize() == 5
    finally:
        tq.close()


def test_telemetry_1_by_1_eviction():
    tq = AsyncTelemetryQueue(maxsize=3, threaded_bridge=False)
    try:
        tq.put_nowait(1)
        tq.put_nowait(2)
        tq.put_nowait(3)
        tq.put_nowait(4)  # drop 1
        tq.put_nowait(5)  # drop 2
        items = []
        while True:
            x = tq.get_nowait()
            if x is None:
                break
            items.append(x)
        assert items == [3, 4, 5]
        assert tq.dropped_count() == 2
    finally:
        tq.close()


def test_no_global_state():
    import src.data_layer.queues.async_state_queue as mod_s
    import src.data_layer.queues.async_telemetry_queue as mod_t

    assert not hasattr(mod_s, "_state_queue_global")
    assert not hasattr(mod_t, "_telemetry_queue_global")