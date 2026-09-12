# YAMA Y-266, Y-269, Y-311, Y-331, Y-353, Y-358

import asyncio
from unittest.mock import patch

import pytest

from src.ws_manager.funding_scheduler import FundingScheduler, FundingSchedulerConfig

def test_config_default_interval_8h():
    cfg = FundingSchedulerConfig()
    assert cfg.funding_interval_ms == 28800000

def test_config_jitter_20():
    cfg = FundingSchedulerConfig()
    assert cfg.funding_jitter_pct == 20

@pytest.mark.asyncio
async def test_start_creates_task():
    cfg = FundingSchedulerConfig(funding_interval_ms=1000000)
    sched = FundingScheduler(cfg)
    await sched.start()
    assert sched._task is not None
    assert isinstance(sched._task, asyncio.Task)
    await sched.stop()

@pytest.mark.asyncio
async def test_start_idempotent():
    cfg = FundingSchedulerConfig(funding_interval_ms=1000000)
    sched = FundingScheduler(cfg)
    await sched.start()
    t1 = sched._task
    await sched.start()
    t2 = sched._task
    assert t1 is t2
    await sched.stop()

@pytest.mark.asyncio
async def test_stop_idempotent():
    cfg = FundingSchedulerConfig(funding_interval_ms=1000000)
    sched = FundingScheduler(cfg)
    await sched.start()
    await sched.stop()
    await sched.stop()
    assert sched._task is None

@pytest.mark.asyncio
async def test_stop_cancels_task():
    cfg = FundingSchedulerConfig(funding_interval_ms=1000000)
    sched = FundingScheduler(cfg)
    await sched.start()
    task = sched._task
    await sched.stop()
    assert task.cancelled() or task.done()

@pytest.mark.asyncio
async def test_task_none_after_stop():
    cfg = FundingSchedulerConfig(funding_interval_ms=1000000)
    sched = FundingScheduler(cfg)
    await sched.start()
    await sched.stop()
    assert sched._task is None

@pytest.mark.asyncio
async def test_loop_respects_running_flag():
    cfg = FundingSchedulerConfig(funding_interval_ms=100)
    sched = FundingScheduler(cfg)
    sched._running = True

    async def fake_sleep(s):
        sched._running = False

    with patch("asyncio.sleep", side_effect=fake_sleep):
        await sched._loop()

def test_no_global_state():
    assert not hasattr(FundingScheduler, "_task")
    assert not hasattr(FundingScheduler, "_running")

@pytest.mark.asyncio
async def test_jitter_applied():
    cfg = FundingSchedulerConfig(funding_interval_ms=1000, funding_jitter_pct=20)
    sched = FundingScheduler(cfg)
    sched._running = True

    sleep_values = []

    async def fake_sleep(s):
        sleep_values.append(s)
        sched._running = False

    with patch("src.ws_manager.funding_scheduler.random.random", return_value=1.0):
        with patch("asyncio.sleep", side_effect=fake_sleep):
            await sched._loop()

    # random=1.0 => jitter_factor = 1 + (1*2-1)*0.2 = 1.2
    assert sleep_values[0] == pytest.approx(1.2, abs=0.01)

@pytest.mark.asyncio
async def test_cancelled_error_handled():
    cfg = FundingSchedulerConfig(funding_interval_ms=1000000)
    sched = FundingScheduler(cfg)
    await sched.start()
    # stop should handle CancelledError
    await sched.stop()
    assert sched._task is None