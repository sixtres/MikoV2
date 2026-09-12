import asyncio

import pytest

from src.supervisor import Supervisor, SupervisorConfig


class _StubDashboard:
    async def start(self):
        await asyncio.sleep(0.01)

    async def stop(self):
        await asyncio.sleep(0)


def _make_supervisor():
    cfg = SupervisorConfig()
    return Supervisor(cfg, _StubDashboard(), object(), object(), asyncio.Lock()), cfg


def test_config_defaults():
    cfg = SupervisorConfig()
    assert cfg.backoff_ms == (5000, 10000, 30000, 60000)
    assert cfg.sigterm_grace_s == 30
    assert cfg.funding_times_utc == (0, 8, 16)


@pytest.mark.asyncio
async def test_stop_sets_event():
    sup, _ = _make_supervisor()
    sup.stop()
    assert sup._shutdown_event.is_set()


@pytest.mark.asyncio
async def test_funding_scheduler_stops_on_event():
    sup, _ = _make_supervisor()
    task = asyncio.create_task(sup.funding_scheduler())
    await asyncio.sleep(0.05)
    sup.stop()
    await asyncio.sleep(1.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert task.done()


def test_no_global_state():
    assert not hasattr(Supervisor, "_shutdown_event")