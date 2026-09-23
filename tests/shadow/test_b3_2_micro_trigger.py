# tests/shadow/test_b3_2_micro_trigger.py
"""B3.2 — MicroTrigger canli entegrasyonu + quarantine testleri.

Kapsam:
  - MicroTrigger quarantine API: is_quarantined / quarantine
  - quarantine emit_event + IDLE reset
  - evaluate quarantine altinda no-op
  - _reset_to_idle quarantine'i sifirlamaz (ortogonal)
  - quarantine suresi dolunca otomatik yeniden aktif
  - ShadowRunner._init_symbol_state idempotent + component init
  - ShadowRunner._determine_direction LONG/SHORT/None
  - _micro_trigger_loop quarantined sembolu atlar
  - _micro_trigger_loop evaluate exception -> quarantine

Mock: yok (in-process). Gercek ag yok.
Kilitli kararlar: DURUM §11 SORU B3.2-A/B/C/D/E.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import replace

import pytest

from src.features.micro_trigger import (
    MicroTrigger,
    MicroTriggerConfig,
    MicroTriggerState,
)
from src.backtest.signal_detector import Signal, SignalKind
from src.backtest.strategy import Direction
from tests.shadow.runner import ShadowRunner


# ---------------------------------------------------------- helpers

def _noop_emit(event_type: str, payload: dict) -> None:
    pass


def _mt(quarantine_ms: int = 60_000, emit=None) -> MicroTrigger:
    return MicroTrigger(
        MicroTriggerConfig(quarantine_ms=quarantine_ms),
        emit or _noop_emit,
    )


def _runner() -> ShadowRunner:
    return ShadowRunner(
        symbols=["BTC_USDT", "ETH_USDT"],
        duration_s=0,
        db_path=None,
        enable_rotation=False,
    )


# ---------------------------------------------------------- MicroTrigger quarantine

def test_is_quarantined_initially_false() -> None:
    mt = _mt()
    assert mt.is_quarantined("BTC_USDT") is False


def test_quarantine_sets_flag_and_resets_state() -> None:
    mt = _mt()
    mt.quarantine("BTC_USDT", "test")
    assert mt.is_quarantined("BTC_USDT") is True
    assert mt.get_state("BTC_USDT") == MicroTriggerState.IDLE


def test_quarantine_emits_event() -> None:
    events: list = []
    mt = _mt(emit=lambda e, p: events.append((e, p)))
    mt.quarantine("BTC_USDT", "my_reason")
    assert len(events) == 1
    evt, payload = events[0]
    assert evt == MicroTrigger.MICRO_TRIGGER_QUARANTINE
    assert payload["symbol"] == "BTC_USDT"
    assert payload["reason"] == "my_reason"
    assert payload["until_ms"] > 0


@pytest.mark.asyncio
async def test_quarantine_expires() -> None:
    mt = _mt(quarantine_ms=50)
    mt.quarantine("BTC_USDT", "test")
    assert mt.is_quarantined("BTC_USDT") is True
    await asyncio.sleep(0.07)
    assert mt.is_quarantined("BTC_USDT") is False


@pytest.mark.asyncio
async def test_evaluate_noop_when_quarantined() -> None:
    mt = _mt()
    mt.quarantine("BTC_USDT", "test")
    state = await mt.evaluate(
        "BTC_USDT", is_valid=True, sweep_detected=True
    )
    assert state == MicroTriggerState.IDLE


def test_reset_to_idle_does_not_clear_quarantine() -> None:
    mt = _mt()
    mt.quarantine("BTC_USDT", "test")
    mt._reset_to_idle("BTC_USDT")
    assert mt.is_quarantined("BTC_USDT") is True


# ---------------------------------------------------------- ShadowRunner init

def test_init_symbol_state_idempotent() -> None:
    r = _runner()
    first = r._micro_triggers["BTC_USDT"]
    r._init_symbol_state("BTC_USDT")
    second = r._micro_triggers["BTC_USDT"]
    assert first is second


def test_init_symbol_state_creates_all_components() -> None:
    r = _runner()
    r._init_symbol_state("SOL_USDT")
    assert "SOL_USDT" in r._mt_detectors
    assert "SOL_USDT" in r._micro_triggers
    assert "SOL_USDT" in r._shadow_strategies
    assert "SOL_USDT" in r._shadow_detectors
    assert "SOL_USDT" in r._recent_signals
    assert r._last_price["SOL_USDT"] == 0.0
    assert r._last_exchange_ts["SOL_USDT"] == 0
    assert r._last_mt_state["SOL_USDT"] == MicroTriggerState.IDLE


# ---------------------------------------------------------- _determine_direction

def test_determine_direction_long() -> None:
    r = _runner()
    recent = deque()
    recent.append((1000, Signal(SignalKind.SWEEP_DOWN, 1000, 100.0)))
    recent.append((1000, Signal(SignalKind.MSS_UP, 1000, 100.0)))
    recent.append((1000, Signal(SignalKind.FVG_BULLISH, 1000, 100.0)))
    assert r._determine_direction("BTC_USDT", recent) == Direction.LONG


def test_determine_direction_short() -> None:
    r = _runner()
    recent = deque()
    recent.append((1000, Signal(SignalKind.SWEEP_UP, 1000, 100.0)))
    recent.append((1000, Signal(SignalKind.MSS_DOWN, 1000, 100.0)))
    recent.append((1000, Signal(SignalKind.FVG_BEARISH, 1000, 100.0)))
    assert r._determine_direction("BTC_USDT", recent) == Direction.SHORT


def test_determine_direction_none_partial_setup() -> None:
    r = _runner()
    recent = deque()
    recent.append((1000, Signal(SignalKind.SWEEP_DOWN, 1000, 100.0)))
    recent.append((1000, Signal(SignalKind.MSS_UP, 1000, 100.0)))
    # FVG eksik
    assert r._determine_direction("BTC_USDT", recent) is None


# ---------------------------------------------------------- _micro_trigger_loop

@pytest.mark.asyncio
async def test_micro_trigger_loop_skips_quarantined() -> None:
    r = _runner()
    # Hizli test: loop timer'ini kisalt
    r._mt_config = replace(r._mt_config, timer_sleep_ms=10)
    # BTC'yi quarantine et
    r._micro_triggers["BTC_USDT"].quarantine("BTC_USDT", "test")

    calls: list[str] = []
    orig_btc = r._micro_triggers["BTC_USDT"].evaluate
    orig_eth = r._micro_triggers["ETH_USDT"].evaluate

    async def mock_eval_btc(*a, **kw):
        calls.append("BTC")
        return await orig_btc(*a, **kw)

    async def mock_eval_eth(*a, **kw):
        calls.append("ETH")
        return await orig_eth(*a, **kw)

    r._micro_triggers["BTC_USDT"].evaluate = mock_eval_btc
    r._micro_triggers["ETH_USDT"].evaluate = mock_eval_eth

    task = asyncio.create_task(r._micro_trigger_loop())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert "BTC" not in calls, f"quarantined symbol evaluated: {calls}"
    assert "ETH" in calls, f"non-quarantined symbol not evaluated: {calls}"


@pytest.mark.asyncio
async def test_micro_trigger_loop_quarantines_on_exception() -> None:
    r = _runner()
    r._mt_config = replace(r._mt_config, timer_sleep_ms=10)

    async def boom(*a, **kw):
        raise RuntimeError("simulated failure")

    r._micro_triggers["BTC_USDT"].evaluate = boom

    task = asyncio.create_task(r._micro_trigger_loop())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert r._micro_triggers["BTC_USDT"].is_quarantined("BTC_USDT") is True