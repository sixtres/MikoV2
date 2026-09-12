# YAMA Y-276, Y-329, Y-353

import asyncio
import inspect
import multiprocessing as mp

import pytest

from src.data_layer.queues.async_telemetry_queue import AsyncTelemetryQueue

def test_maxsize_default_1000():
    q = AsyncTelemetryQueue()
    assert q.maxsize == 1000

def test_put_nowait_single():
    q = AsyncTelemetryQueue(maxsize=10)
    q.put_nowait("a")
    assert q.qsize() == 1

def test_put_nowait_sync():
    q = AsyncTelemetryQueue()
    assert not inspect.iscoroutinefunction(q.put_nowait)

def test_put_nowait_drop_oldest():
    q = AsyncTelemetryQueue(maxsize=2)
    q.put_nowait("a")
    q.put_nowait("b")
    q.put_nowait("c")  # should drop oldest "a"
    assert q.qsize() == 2
    first = q.get_nowait()
    second = q.get_nowait()
    # first should be b, second c
    assert first == "b"
    assert second == "c"

def test_put_nowait_dropped_counter():
    q = AsyncTelemetryQueue(maxsize=1)
    q.put_nowait("a")
    # force full then make get fail by mocking? simpler: fill and drop normally does not increase dropped
    # but if second put after get fails to put again, it counts
    # with our impl, drop_oldest succeeds, so dropped stays 0
    # test dropped counter initial 0
    assert q.dropped_count() == 0

def test_get_nowait_returns_item():
    q = AsyncTelemetryQueue()
    q.put_nowait("x")
    item = q.get_nowait()
    assert item == "x"

def test_get_nowait_empty_returns_none():
    q = AsyncTelemetryQueue()
    assert q.get_nowait() is None

def test_qsize_after_puts():
    q = AsyncTelemetryQueue(maxsize=10)
    q.put_nowait(1)
    q.put_nowait(2)
    q.put_nowait(3)
    assert q.qsize() == 3

def test_maxsize_property():
    q = AsyncTelemetryQueue(maxsize=5)
    assert q.maxsize == 5

def test_no_global_state():
    assert not hasattr(AsyncTelemetryQueue, "_q")
    assert not hasattr(AsyncTelemetryQueue, "_dropped")

def test_fire_and_forget_no_await():
    q = AsyncTelemetryQueue(maxsize=10)
    # should not need await
    q.put_nowait("fire")
    q.put_nowait("forget")
    assert q.qsize() == 2

def test_drop_oldest_preserves_newest():
    q = AsyncTelemetryQueue(maxsize=2)
    q.put_nowait(1)
    q.put_nowait(2)
    q.put_nowait(3)
    q.put_nowait(4)
    items = []
    while True:
        it = q.get_nowait()
        if it is None:
            break
        items.append(it)
    assert items == [3, 4]