# YAMA Y-255: paused_ms float accumulate even invalid
# YAMA Y-256: fresh_tick_event defaultdict safe get
# YAMA Y-257: next_candle extrapolate max(0, mono_now - last_mono) + 5000
# YAMA Y-280: hard deadline is_valid=False iken de tetiklenir
# YAMA Y-294: reset_to_idle paused_ms last_seen_tick_seq
# YAMA Y-306: reset sirasi emit -> reset -> cleanup
# YAMA Y-344: OBI aktif len
# YAMA Y-353: DI, no global
# YAMA Y-358: asyncio.Lock
# SORU B3.2-D: sembol bazli quarantine + is_quarantined API

"""
Micro trigger - FVG_OTE state machine + hard deadline + paused accumulation.

States (ascending priority):
  IDLE -> SWEEP -> MSS -> FVG_OTE -> MICRO_CONFIRM -> TRIGGER

Per-symbol state. Timer cancellable. Paused_ms accumulates even when
input is invalid (Y-255). Hard deadline 600000 ms (Y-280) fires
FVG_EXPIRED_HARD_DEADLINE regardless of validity.

SORU B3.2-D: quarantine — sembol bazli devre disi birakma, global
shutdown yok. quarantine_until_ms monotonik; suresi dolunca sembol
otomatik yeniden aktif.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class MicroTriggerState(str, Enum):
    IDLE = "IDLE"
    SWEEP = "SWEEP"
    MSS = "MSS"
    FVG_OTE = "FVG_OTE"
    MICRO_CONFIRM = "MICRO_CONFIRM"
    TRIGGER = "TRIGGER"


_STATE_RANK = {
    MicroTriggerState.IDLE: 0,
    MicroTriggerState.SWEEP: 1,
    MicroTriggerState.MSS: 2,
    MicroTriggerState.FVG_OTE: 3,
    MicroTriggerState.MICRO_CONFIRM: 4,
    MicroTriggerState.TRIGGER: 5,
}


@dataclass(frozen=True, slots=True)
class MicroTriggerConfig:
    sweep_equal_pct: float = 0.0008
    wick_ratio: float = 0.6
    mss_timeout_ms: int = 90_000
    fvg_timeout_ms: int = 180_000
    fvg_ote_low: float = 0.62
    fvg_ote_high: float = 0.79
    tolerance: float = 0.015
    min_size_pct: float = 0.0005
    breach_ms: int = 15_000
    micro_candle_ms: int = 5_000
    hard_deadline_ms: int = 600_000
    next_candle_buffer_ms: int = 5_000
    timer_sleep_ms: int = 5_000
    quarantine_ms: int = 60_000


@dataclass(slots=True)
class SymbolTriggerState:
    state: MicroTriggerState = MicroTriggerState.IDLE
    sweep_started_ms: int = 0
    mss_confirmed_ms: int = 0
    fvg_detected_ms: int = 0
    breach_start_ms: int = 0
    paused_ms: float = 0.0
    pause_start_ms: int = 0
    next_candle_target_ms: int = 0
    last_exchange_ts_ms: int = 0
    last_mono_ms: int = 0
    was_paused: bool = False
    quarantine_until_ms: int = 0  # SORU B3.2-D: monotonik ms


def _monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


def _wall_ms() -> int:
    return int(time.time() * 1000)


class MicroTrigger:
    """
    Micro trigger state machine.

    emit_event: sync callback (event_type: str, payload: dict) -> None
    event_type constants are strings, caller decides dispatch.
    """

    FVG_EXPIRED_HARD_DEADLINE = "FVG_EXPIRED_HARD_DEADLINE"
    FVG_INVALIDATED = "FVG_INVALIDATED"
    MICRO_TRIGGER_QUARANTINE = "MICRO_TRIGGER_QUARANTINE"

    def __init__(
        self,
        config: MicroTriggerConfig,
        emit_event: Callable[[str, dict], None],
    ) -> None:
        self._config = config
        self._emit = emit_event
        self._states: dict[str, SymbolTriggerState] = defaultdict(SymbolTriggerState)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._fresh_tick: dict[str, asyncio.Event] = {}

    # --------------------------------------------------------------- helpers

    def _now_mono(self) -> int:
        return _monotonic_ms()

    def _get_fresh_tick_event(self, symbol: str) -> asyncio.Event:
        """Y-256: safe get, not KeyError."""
        ev = self._fresh_tick.get(symbol)
        if ev is None:
            ev = asyncio.Event()
            self._fresh_tick[symbol] = ev
        return ev

    def _transition(
        self, symbol: str, new_state: MicroTriggerState, reason: str
    ) -> bool:
        """Ascending-only transition. Returns True if changed."""
        st = self._states[symbol]
        if _STATE_RANK[new_state] > _STATE_RANK[st.state]:
            st.state = new_state
            self._emit(
                new_state.value,
                {"symbol": symbol, "reason": reason},
            )
            return True
        return False

    def _reset_to_idle(self, symbol: str) -> None:
        """Y-294: reset resets paused_ms ve last_seen.

        SORU B3.2-D: quarantine_until_ms ortogonal; reset etkilenmez.
        """
        st = self._states[symbol]
        st.state = MicroTriggerState.IDLE
        st.sweep_started_ms = 0
        st.mss_confirmed_ms = 0
        st.fvg_detected_ms = 0
        st.breach_start_ms = 0
        st.pause_start_ms = 0
        st.paused_ms = 0.0
        st.next_candle_target_ms = 0
        st.was_paused = False
        ev = self._fresh_tick.get(symbol)
        if ev is not None:
            ev.set()

    def get_state(self, symbol: str) -> MicroTriggerState:
        return self._states[symbol].state

    def get_paused_ms(self, symbol: str) -> float:
        return self._states[symbol].paused_ms

    # --------------------------------------------------------------- quarantine
    # SORU B3.2-D: sembol bazli devre disi birakma.

    def is_quarantined(self, symbol: str) -> bool:
        """Sembol su anda quarantine altinda mi?"""
        return self._states[symbol].quarantine_until_ms > _monotonic_ms()

    def quarantine(self, symbol: str, reason: str) -> None:
        """Sembolu quarantine_ms boyunca devre disi birak; state IDLE'a doner.

        Global shutdown yok (SORU B3.2-D=A).
        """
        st = self._states[symbol]
        until = _monotonic_ms() + self._config.quarantine_ms
        st.quarantine_until_ms = until
        st.state = MicroTriggerState.IDLE
        logger.warning(
            "MICRO_TRIGGER_QUARANTINE symbol=%s reason=%s until_ms=%d",
            symbol, reason, until,
        )
        self._emit(
            self.MICRO_TRIGGER_QUARANTINE,
            {"symbol": symbol, "reason": reason, "until_ms": until},
        )

    # --------------------------------------------------------------- timer

    async def cancellable_sleep(
        self,
        symbol: str,
        timeout_ms: int,
        shutdown_event: asyncio.Event | None = None,
    ) -> None:
        """Sleep but wake up early if fresh tick OR shutdown arrives."""
        ev = self._get_fresh_tick_event(symbol)
        ev.clear()

        if shutdown_event is None:
            try:
                await asyncio.wait_for(ev.wait(), timeout=timeout_ms / 1000.0)
            except asyncio.TimeoutError:
                pass
            return

        # race between fresh_tick, shutdown, and timeout
        wait_fresh = asyncio.ensure_future(ev.wait())
        wait_shutdown = asyncio.ensure_future(shutdown_event.wait())
        try:
            await asyncio.wait_for(
                asyncio.wait(
                    {wait_fresh, wait_shutdown},
                    return_when=asyncio.FIRST_COMPLETED,
                ),
                timeout=timeout_ms / 1000.0,
            )
        except asyncio.TimeoutError:
            pass
        finally:
            for fut in (wait_fresh, wait_shutdown):
                if not fut.done():
                    fut.cancel()
            # swallow cancellation
            for fut in (wait_fresh, wait_shutdown):
                try:
                    await fut
                except (asyncio.CancelledError, Exception):
                    pass

    def signal_fresh_tick(self, symbol: str) -> None:
        """Called by ws_manager when a new valid tick arrives."""
        ev = self._get_fresh_tick_event(symbol)
        ev.set()

    # --------------------------------------------------------------- state entry

    async def evaluate(
        self,
        symbol: str,
        *,
        is_valid: bool,
        sweep_detected: bool = False,
        mss_detected: bool = False,
        fvg_detected: bool = False,
        micro_confirmed: bool = False,
        exchange_ts_ms: int = 0,
        current_position_qty: float = 0.0,
    ) -> MicroTriggerState:
        """
        Run one evaluation cycle for a symbol.

        Returns the (possibly new) state.
        """
        cfg = self._config
        async with self._locks[symbol]:
            st = self._states[symbol]
            now_mono = self._now_mono()
            now_wall = _wall_ms()

            # SORU B3.2-D: quarantine altinda evaluate no-op.
            if st.quarantine_until_ms > now_mono:
                return st.state

            # Y-280 / Y-306: hard deadline fires even when is_valid=False
            if (
                st.paused_ms >= cfg.hard_deadline_ms
                and st.state not in (MicroTriggerState.IDLE,)
            ):
                self._emit(
                    self.FVG_EXPIRED_HARD_DEADLINE,
                    {"symbol": symbol, "paused_ms": int(st.paused_ms)},
                )
                self._reset_to_idle(symbol)
                return MicroTriggerState.IDLE

            # invalid input: accumulate paused_ms
            if not is_valid:
                if st.pause_start_ms == 0:
                    st.pause_start_ms = now_mono
                else:
                    st.paused_ms += (now_mono - st.pause_start_ms)
                    st.pause_start_ms = now_mono
                st.was_paused = True
                return st.state

            # valid input: flush pause if any
            if st.pause_start_ms != 0:
                st.paused_ms += (now_mono - st.pause_start_ms)
                st.pause_start_ms = 0

            # update time anchors
            if exchange_ts_ms:
                st.last_exchange_ts_ms = exchange_ts_ms
                st.last_mono_ms = now_mono
                st.next_candle_target_ms = (
                    exchange_ts_ms
                    + max(0, now_mono - st.last_mono_ms)
                    + cfg.next_candle_buffer_ms
                )

            # state progression
            if st.state == MicroTriggerState.IDLE and sweep_detected:
                st.sweep_started_ms = now_wall
                self._transition(symbol, MicroTriggerState.SWEEP, "sweep")
            elif st.state == MicroTriggerState.SWEEP and mss_detected:
                st.mss_confirmed_ms = now_wall
                self._transition(symbol, MicroTriggerState.MSS, "mss")
            elif st.state == MicroTriggerState.MSS and fvg_detected:
                st.fvg_detected_ms = now_wall
                self._transition(symbol, MicroTriggerState.FVG_OTE, "fvg_ote")
            elif st.state == MicroTriggerState.FVG_OTE and micro_confirmed:
                self._transition(
                    symbol, MicroTriggerState.MICRO_CONFIRM, "micro"
                )
            elif st.state == MicroTriggerState.MICRO_CONFIRM and micro_confirmed:
                self._transition(symbol, MicroTriggerState.TRIGGER, "trigger")

            return st.state

    # --------------------------------------------------------------- loop

    async def run_loop(
        self,
        symbols: list[str],
        tick_provider: Callable[[str], Awaitable[Any]],
        shutdown_event: asyncio.Event,
    ) -> None:
        """
        Main timer loop. Supervisor launches this as a task.

        tick_provider(symbol) must return an object with fields:
          is_valid: bool
          sweep_detected: bool
          mss_detected: bool
          fvg_detected: bool
          micro_confirmed: bool
          exchange_ts_ms: int
          current_position_qty: float
        or None (means no tick yet).
        """
        while not shutdown_event.is_set():
            for symbol in symbols:
                if shutdown_event.is_set():
                    break
                # SORU B3.2-D: quarantined sembolu atla
                if self.is_quarantined(symbol):
                    continue
                try:
                    tick = await tick_provider(symbol)
                except Exception as e:
                    logger.warning("tick_provider failed symbol=%s err=%s", symbol, e)
                    continue

                if tick is None:
                    await self.cancellable_sleep(
                        symbol, self._config.timer_sleep_ms, shutdown_event
                    )
                    continue

                try:
                    await self.evaluate(
                        symbol,
                        is_valid=getattr(tick, "is_valid", True),
                        sweep_detected=getattr(tick, "sweep_detected", False),
                        mss_detected=getattr(tick, "mss_detected", False),
                        fvg_detected=getattr(tick, "fvg_detected", False),
                        micro_confirmed=getattr(tick, "micro_confirmed", False),
                        exchange_ts_ms=getattr(tick, "exchange_ts_ms", 0),
                        current_position_qty=getattr(
                            tick, "current_position_qty", 0.0
                        ),
                    )
                except Exception as e:
                    logger.warning(
                        "evaluate failed symbol=%s err=%s", symbol, e
                    )
                    self.quarantine(symbol, "evaluate_error")

                await self.cancellable_sleep(
                    symbol, self._config.timer_sleep_ms, shutdown_event
                )