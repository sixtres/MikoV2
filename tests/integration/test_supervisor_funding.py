"""
Supervisor + funding scheduler integration tests.
Y-266 SIGTERM grace, Y-331 funding 00/08/16 UTC ayrı task, backoff.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from src.supervisor import Supervisor, SupervisorConfig
from src.ws_manager.funding_scheduler import FundingScheduler, FundingSchedulerConfig


class _StubDashboard:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.start_event = asyncio.Event()

    async def start(self):
        self.started = True
        self.start_event.set()
        # Block until cancelled (like real dashboard serving)
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise

    async def stop(self):
        self.stopped = True


def _make_supervisor():
    cfg = SupervisorConfig(
        backoff_ms=(100, 200, 300, 400),
        sigterm_grace_s=1,
        funding_times_utc=(0, 8, 16),
    )
    dashboard = _StubDashboard()
    return Supervisor(cfg, dashboard, MagicMock(), MagicMock(), asyncio.Lock()), dashboard


def test_supervisor_config_defaults():
    cfg = SupervisorConfig()
    assert cfg.backoff_ms == (5000, 10000, 30000, 60000)
    assert cfg.sigterm_grace_s == 30
    assert cfg.funding_times_utc == (0, 8, 16)


def test_funding_scheduler_config_8h():
    cfg = FundingSchedulerConfig()
    assert cfg.funding_interval_ms == 28800000  # 8h = 00/08/16 UTC
    assert cfg.funding_jitter_pct == 20


def test_funding_interval_matches_utc_schedule():
    # 3 times per day: 00, 08, 16 UTC = 8h interval
    cfg = FundingSchedulerConfig()
    hours = cfg.funding_interval_ms / 3600000.0
    assert hours == 8.0


@pytest.mark.asyncio
async def test_funding_scheduler_start_idempotent():
    cfg = FundingSchedulerConfig(funding_interval_ms=100000)
    sched = FundingScheduler(cfg)
    await sched.start()
    t1 = sched._task
    assert t1 is not None
    await sched.start()
    t2 = sched._task
    assert t1 is t2  # idempotent
    await sched.stop()


@pytest.mark.asyncio
async def test_funding_scheduler_stop_cancels_task():
    cfg = FundingSchedulerConfig(funding_interval_ms=100000)
    sched = FundingScheduler(cfg)
    await sched.start()
    task = sched._task
    await sched.stop()
    assert task.done() or task.cancelled()
    assert sched._task is None


@pytest.mark.asyncio
async def test_funding_scheduler_stop_idempotent():
    cfg = FundingSchedulerConfig(funding_interval_ms=100000)
    sched = FundingScheduler(cfg)
    await sched.start()
    await sched.stop()
    await sched.stop()  # second stop safe
    assert sched._task is None


@pytest.mark.asyncio
async def test_supervisor_runs_and_stops():
    sup, dashboard = _make_supervisor()
    run_task = asyncio.create_task(sup.run())
    await asyncio.wait_for(dashboard.start_event.wait(), timeout=2)
    assert dashboard.started is True

    sup.stop()
    try:
        await asyncio.wait_for(run_task, timeout=3)
    except asyncio.TimeoutError:
        run_task.cancel()
        pytest.fail("supervisor.run() did not return after stop()")


@pytest.mark.asyncio
async def test_supervisor_stop_sets_event():
    sup, _ = _make_supervisor()
    assert not sup._shutdown_event.is_set()
    sup.stop()
    assert sup._shutdown_event.is_set()


@pytest.mark.asyncio
async def test_supervisor_stop_idempotent():
    sup, _ = _make_supervisor()
    sup.stop()
    sup.stop()
    sup.stop()
    assert sup._shutdown_event.is_set()


@pytest.mark.asyncio
async def test_supervisor_task_cleanup_on_shutdown():
    sup, dashboard = _make_supervisor()
    run_task = asyncio.create_task(sup.run())
    await asyncio.wait_for(dashboard.start_event.wait(), timeout=2)
    sup.stop()
    try:
        await asyncio.wait_for(run_task, timeout=3)
    except asyncio.TimeoutError:
        run_task.cancel()
        pytest.fail("run() hung")
    # dashboard.stop should have been called in cleanup
    assert dashboard.stopped is True
    # tasks list cleared
    assert len(sup._tasks) == 0


def test_supervisor_no_global_state():
    assert not hasattr(Supervisor, "_shutdown_event")
    assert not hasattr(Supervisor, "_tasks")
    assert not hasattr(Supervisor, "_dashboard")


def test_funding_scheduler_no_global_state():
    assert not hasattr(FundingScheduler, "_task")
    assert not hasattr(FundingScheduler, "_running")
    assert not hasattr(FundingScheduler, "_lock")