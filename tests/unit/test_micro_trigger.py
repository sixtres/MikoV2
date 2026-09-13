# YAMA Y-255, Y-256, Y-257, Y-280, Y-294, Y-306, Y-353

import asyncio
from unittest.mock import MagicMock

import pytest

from src.features.micro_trigger import (
    MicroTrigger,
    MicroTriggerConfig,
    MicroTriggerState,
    SymbolTriggerState,
)


def _make_trigger(emit=None, **cfg_over):
    if emit is None:
        emit = MagicMock()
    cfg = MicroTriggerConfig(**cfg_over)
    return MicroTrigger(cfg, emit), emit


def test_config_defaults():
    cfg = MicroTriggerConfig()
    assert cfg.sweep_equal_pct == 0.0008
    assert cfg.hard_deadline_ms == 600_000
    assert cfg.timer_sleep_ms == 5_000
    assert cfg.breach_ms == 15_000


def test_no_global_state():
    assert not hasattr(MicroTrigger, "_states")
    assert not hasattr(MicroTrigger, "_locks")


def test_initial_state_idle():
    t, _ = _make_trigger()
    assert t.get_state("BTC_USDT") == MicroTriggerState.IDLE


@pytest.mark.asyncio
async def test_state_progression_full():
    t, _ = _make_trigger()
    sym = "BTC_USDT"
    await t.evaluate(sym, is_valid=True, sweep_detected=True)
    assert t.get_state(sym) == MicroTriggerState.SWEEP
    await t.evaluate(sym, is_valid=True, mss_detected=True)
    assert t.get_state(sym) == MicroTriggerState.MSS
    await t.evaluate(sym, is_valid=True, fvg_detected=True)
    assert t.get_state(sym) == MicroTriggerState.FVG_OTE
    await t.evaluate(sym, is_valid=True, micro_confirmed=True)
    assert t.get_state(sym) == MicroTriggerState.MICRO_CONFIRM
    await t.evaluate(sym, is_valid=True, micro_confirmed=True)
    assert t.get_state(sym) == MicroTriggerState.TRIGGER


@pytest.mark.asyncio
async def test_state_does_not_regress():
    """Older state signal cannot drop back to IDLE by re-emitting lower state."""
    t, _ = _make_trigger()
    sym = "BTC_USDT"
    await t.evaluate(sym, is_valid=True, sweep_detected=True)
    await t.evaluate(sym, is_valid=True, mss_detected=True)
    assert t.get_state(sym) == MicroTriggerState.MSS
    # try to send sweep again — should stay MSS (no regression)
    await t.evaluate(sym, is_valid=True, sweep_detected=True)
    assert t.get_state(sym) == MicroTriggerState.MSS


@pytest.mark.asyncio
async def test_paused_ms_accumulates_when_invalid():
    t, _ = _make_trigger()
    sym = "BTC_USDT"
    await t.evaluate(sym, is_valid=True, sweep_detected=True)
    # invalid -> paused
    await t.evaluate(sym, is_valid=False)
    # wait, still invalid
    await asyncio.sleep(0.05)
    await t.evaluate(sym, is_valid=False)
    paused = t.get_paused_ms(sym)
    assert paused >= 0


@pytest.mark.asyncio
async def test_hard_deadline_fires_when_invalid():
    """Y-280: hard deadline fires even when input invalid."""
    emit = MagicMock()
    t, _ = _make_trigger(emit=emit, hard_deadline_ms=0)
    sym = "BTC_USDT"
    await t.evaluate(sym, is_valid=True, sweep_detected=True)
    assert t.get_state(sym) == MicroTriggerState.SWEEP

    # force paused_ms high by setting state directly
    t._states[sym].paused_ms = 999_999.0
    await t.evaluate(sym, is_valid=False)

    assert t.get_state(sym) == MicroTriggerState.IDLE
    # FVG_EXPIRED_HARD_DEADLINE emit should have been called
    emit.assert_any_call(
        "FVG_EXPIRED_HARD_DEADLINE",
        {"symbol": sym, "paused_ms": 999_999},
    )


@pytest.mark.asyncio
async def test_reset_to_idle_clears_state():
    t, _ = _make_trigger()
    sym = "BTC_USDT"
    await t.evaluate(sym, is_valid=True, sweep_detected=True)
    await t.evaluate(sym, is_valid=True, mss_detected=True)
    st = t._states[sym]
    assert st.state == MicroTriggerState.MSS
    t._reset_to_idle(sym)
    assert t.get_state(sym) == MicroTriggerState.IDLE
    assert st.paused_ms == 0.0
    assert st.sweep_started_ms == 0


@pytest.mark.asyncio
async def test_fresh_tick_event_safe_get():
    """Y-256: fresh_tick_event safe get, no KeyError."""
    t, _ = _make_trigger()
    ev = t._get_fresh_tick_event("NEVER_SEEN")
    assert isinstance(ev, asyncio.Event)
    ev2 = t._get_fresh_tick_event("NEVER_SEEN")
    assert ev is ev2


@pytest.mark.asyncio
async def test_cancellable_sleep_wakes_early():
    t, _ = _make_trigger()
    sym = "BTC_USDT"
    start = asyncio.get_event_loop().time()

    async def wake_soon():
        await asyncio.sleep(0.02)
        t.signal_fresh_tick(sym)

    asyncio.create_task(wake_soon())
    await t.cancellable_sleep(sym, timeout_ms=5000)
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_cancellable_sleep_times_out():
    t, _ = _make_trigger()
    sym = "BTC_USDT"
    start = asyncio.get_event_loop().time()
    await t.cancellable_sleep(sym, timeout_ms=50)
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed >= 0.04


@pytest.mark.asyncio
async def test_next_candle_extrapolation():
    """Y-257: next_candle = exchange_ts + max(0, mono_now - last_mono) + 5000."""
    t, _ = _make_trigger()
    sym = "BTC_USDT"
    exchange_ts = 1_000_000
    await t.evaluate(sym, is_valid=True, exchange_ts_ms=exchange_ts)
    st = t._states[sym]
    assert st.last_exchange_ts_ms == exchange_ts
    assert st.next_candle_target_ms >= exchange_ts
    assert st.next_candle_target_ms >= exchange_ts + 5000


@pytest.mark.asyncio
async def test_multi_symbol_independent():
    t, _ = _make_trigger()
    await t.evaluate("BTC_USDT", is_valid=True, sweep_detected=True)
    await t.evaluate("ETH_USDT", is_valid=True)
    assert t.get_state("BTC_USDT") == MicroTriggerState.SWEEP
    assert t.get_state("ETH_USDT") == MicroTriggerState.IDLE


@pytest.mark.asyncio
async def test_loop_runs_and_stops():
    t, _ = _make_trigger()
    shutdown = asyncio.Event()

    async def tick_provider(symbol):
        return None

    task = asyncio.create_task(
        t.run_loop(["BTC_USDT"], tick_provider, shutdown)
    )
    await asyncio.sleep(0.1)
    shutdown.set()
    await asyncio.wait_for(task, timeout=3.0)
    assert task.done()