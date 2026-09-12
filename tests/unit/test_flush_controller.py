# YAMA Y-264, Y-276, Y-310, Y-346, Y-350, Y-356, Y-358, Y-362, Y-368

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

from src.execution.flush_controller import FlushController, FlushControllerConfig

def test_config_default_queue_size_5():
    cfg = FlushControllerConfig()
    assert cfg.bounded_queue_size == 5

def test_suspend_increments_counter():
    cfg = FlushControllerConfig()
    fc = FlushController(cfg)
    fc.suspend()
    assert fc._counter == 1
    fc.suspend()
    assert fc._counter == 2

def test_suspend_idempotent_event_clear_once():
    cfg = FlushControllerConfig()
    fc = FlushController(cfg)
    fc._async_event = MagicMock()
    fc._async_event.clear = MagicMock()
    fc._async_event.set = MagicMock()
    fc.suspend()
    assert fc._async_event.clear.call_count == 1
    fc.suspend()
    assert fc._async_event.clear.call_count == 1

def test_resume_decrements_counter():
    cfg = FlushControllerConfig()
    fc = FlushController(cfg)
    fc.suspend()
    fc.suspend()
    assert fc._counter == 2
    fc.resume()
    assert fc._counter == 1

def test_resume_counter_zero_event_set():
    cfg = FlushControllerConfig()
    fc = FlushController(cfg)
    fc._async_event = MagicMock()
    fc._async_event.clear = MagicMock()
    fc._async_event.set = MagicMock()
    fc.suspend()
    fc.resume()
    assert fc._async_event.set.call_count == 1
    assert fc._counter == 0

def test_resume_underflow_warning():
    cfg = FlushControllerConfig()
    fc = FlushController(cfg)
    with patch("src.execution.flush_controller.logger") as mock_logger:
        fc.resume()
        mock_logger.warning.assert_called()
        assert "FLUSH_COUNTER_UNDERFLOW" in str(mock_logger.warning.call_args)
    assert fc._counter == 0

def test_resume_max_zero_forbidden():
    cfg = FlushControllerConfig()
    fc = FlushController(cfg)
    # implementation must do _counter -=1 then check <0, not max(0, counter-1)
    fc._counter = 0
    with patch("src.execution.flush_controller.logger"):
        fc.resume()
    assert fc._counter == 0
    # check source does not contain max(0,
    import inspect

    src = inspect.getsource(fc.resume)
    assert "max(0" not in src

def test_no_assert_in_prod():
    import inspect

    from src.execution import flush_controller

    src = inspect.getsource(flush_controller.FlushController)
    # no assert in production code
    # filter out test code, only check file
    lines = src.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("assert "):
            raise AssertionError("assert found in prod: %s" % line)

def test_is_suspended_true_false():
    cfg = FlushControllerConfig()
    fc = FlushController(cfg)
    assert fc.is_suspended() is False
    fc.suspend()
    assert fc.is_suspended() is True
    fc.resume()
    assert fc.is_suspended() is False

def test_try_enqueue_flush_ok():
    cfg = FlushControllerConfig(bounded_queue_size=5)
    fc = FlushController(cfg)
    ok = fc.try_enqueue_flush({"a": 1})
    assert ok is True
    assert fc._force_flush_queue.qsize() == 1

def test_try_enqueue_flush_full_returns_false():
    cfg = FlushControllerConfig(bounded_queue_size=5)
    fc = FlushController(cfg)
    for i in range(5):
        assert fc.try_enqueue_flush(i) is True
    assert fc.try_enqueue_flush(6) is False

@pytest.mark.asyncio
async def test_force_flush_daemon_runs():
    cfg = FlushControllerConfig()
    fc = FlushController(cfg)
    task = asyncio.create_task(fc.force_flush_daemon(worker_id=0))
    await asyncio.sleep(0.25)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert task.done()

def test_no_global_state():
    assert not hasattr(FlushController, "_counter")
    assert not hasattr(FlushController, "_force_flush_queue")

def test_single_counter_only():
    cfg = FlushControllerConfig()
    fc = FlushController(cfg)
    # Y-356: tek sayac, cift sayac yasak
    assert hasattr(fc, "_counter")
    assert not hasattr(fc, "_counter_original")
    assert not hasattr(fc, "_counter2")

def test_threading_lock_exception():
    cfg = FlushControllerConfig()
    fc = FlushController(cfg)
    assert type(fc._lock).__name__ == "lock"