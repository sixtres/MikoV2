# YAMA Y-276, Y-329, Y-353

import inspect
import time

import pytest

from src.data_layer.queues.async_telemetry_queue import AsyncTelemetryQueue


def _make(maxsize=1000):
    return AsyncTelemetryQueue(maxsize=maxsize, threaded_bridge=False)


def test_maxsize_default_1000():
    q = _make()
    assert q.maxsize == 1000
    q.close()


def test_put_nowait_single():
    q = _make(maxsize=10)
    try:
        q.put_nowait("a")
        assert q.qsize() == 1
    finally:
        q.close()


def test_put_nowait_sync():
    q = _make()
    try:
        assert not inspect.iscoroutinefunction(q.put_nowait)
    finally:
        q.close()


def test_put_nowait_drop_oldest():
    q = _make(maxsize=2)
    try:
        q.put_nowait("a")
        q.put_nowait("b")
        q.put_nowait("c")  # drop oldest "a"
        assert q.qsize() == 2
        first = q.get_nowait()
        second = q.get_nowait()
        assert first == "b"
        assert second == "c"
    finally:
        q.close()


def test_put_nowait_dropped_counter():
    q = _make(maxsize=1)
    try:
        q.put_nowait("a")
        assert q.dropped_count() == 0
    finally:
        q.close()


@pytest.mark.asyncio
async def test_get_nowait_returns_item():
    q = _make()
    try:
        q.put_nowait("x")
        # mp.Queue feeder thread is async; give it a moment
        import time
        time.sleep(0.05)
        item = q.get_nowait()
        assert item == "x"
    finally:
        q.close()


def test_get_nowait_empty_returns_none():
    q = _make()
    try:
        assert q.get_nowait() is None
    finally:
        q.close()


def test_qsize_after_puts():
    q = _make(maxsize=10)
    try:
        q.put_nowait(1)
        q.put_nowait(2)
        q.put_nowait(3)
        assert q.qsize() == 3
    finally:
        q.close()


def test_maxsize_property():
    q = _make(maxsize=5)
    try:
        assert q.maxsize == 5
    finally:
        q.close()


def test_no_global_state():
    assert not hasattr(AsyncTelemetryQueue, "_q")
    assert not hasattr(AsyncTelemetryQueue, "_dropped")


def test_fire_and_forget_no_await():
    q = _make(maxsize=10)
    try:
        q.put_nowait("fire")
        q.put_nowait("forget")
        assert q.qsize() == 2
    finally:
        q.close()


def test_drop_oldest_preserves_newest():
    q = _make(maxsize=2)
    try:
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
    finally:
        q.close()