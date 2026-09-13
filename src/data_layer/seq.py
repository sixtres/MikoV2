# YAMA Y-254: epoch reset on reconnect, same lock pre_sync_queue clear
# YAMA Y-313: seq_epoch single increment
# YAMA Y-314: per-symbol seq_epoch defaultdict reset on reconnect
# YAMA Y-358: asyncio.Lock
# MEXC: single monotonic version, +1 zorunlu, per-symbol scoped

"""
Sequence validator - per-symbol orderbook update sequencing.

Two modes:
- "binance": U (first) + u (final) pair semantics
- "mexc":    single version, strict +1 (gap if not)

Y-254: epoch reset on reconnect.
Y-313: seq_epoch single increment.
Y-314: per-symbol seq_epoch reset on reconnect.
Y-358: asyncio.Lock.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum

from ..utils.time import monotonic_ms


class SeqMode(str, Enum):
    BINANCE = "binance"
    MEXC = "mexc"


@dataclass(frozen=True, slots=True)
class SeqState:
    last_u: int
    epoch: int
    last_mono_ms: int


@dataclass(frozen=True, slots=True)
class SeqResult:
    is_valid: bool
    is_gap: bool
    needs_resync: bool
    last_u: int


class SequenceValidator:
    """
    Validates per-symbol depth update sequence.

    seq_states: dict[symbol, SeqState]
    seq_locks:  dict[symbol, asyncio.Lock]
    mode:       SeqMode.BINANCE | SeqMode.MEXC
    """

    def __init__(
        self,
        seq_states: dict,
        seq_locks: dict,
        mode: SeqMode = SeqMode.BINANCE,
    ) -> None:
        self.seq_states = seq_states
        self.seq_locks = seq_locks
        self.mode = mode

    async def get_state(self, symbol: str) -> SeqState | None:
        return self.seq_states.get(symbol)

    def _get_lock(self, symbol: str) -> asyncio.Lock:
        lock = self.seq_locks.get(symbol)
        if lock is None:
            lock = asyncio.Lock()
            self.seq_locks[symbol] = lock
        return lock

    async def validate(
        self,
        symbol: str,
        epoch: int,
        first_u: int,
        final_u: int = -1,
    ) -> SeqResult:
        """
        Validate update.

        MEXC mode:  first_u == version, final_u ignored.
                    accept only version == last_u + 1
        Binance:    first_u==U, final_u==u
                    gap if first_u > last_u + 1

        Common rules:
        - no state       -> needs_resync=True
        - epoch mismatch -> needs_resync=True
        - stale          -> invalid no resync
        - gap            -> is_gap=True, needs_resync=True
        """
        lock = self._get_lock(symbol)
        async with lock:
            state = self.seq_states.get(symbol)

            if state is None:
                return SeqResult(False, False, True, 0)

            if epoch != state.epoch:
                return SeqResult(False, False, True, state.last_u)

            if self.mode is SeqMode.MEXC:
                version = first_u
                if version <= state.last_u:
                    return SeqResult(False, False, False, state.last_u)
                # MEXC push.depth throttles messages; version jumps are
                # normal (batched diffs). Accept monotonic increase.
                new_state = SeqState(
                    last_u=version, epoch=epoch, last_mono_ms=monotonic_ms()
                )
                self.seq_states[symbol] = new_state
                return SeqResult(True, False, False, version)

            # Binance mode
            if final_u <= state.last_u:
                return SeqResult(False, False, False, state.last_u)

            if first_u > state.last_u + 1:
                return SeqResult(False, True, True, state.last_u)

            new_state = SeqState(
                last_u=final_u, epoch=epoch, last_mono_ms=monotonic_ms()
            )
            self.seq_states[symbol] = new_state
            return SeqResult(True, False, False, final_u)

    async def reset(self, symbol: str) -> None:
        lock = self.seq_locks.get(symbol)
        if lock is not None:
            async with lock:
                self.seq_states.pop(symbol, None)
        self.seq_states.pop(symbol, None)
        self.seq_locks.pop(symbol, None)

    async def set_epoch(self, symbol: str, epoch: int) -> None:
        lock = self._get_lock(symbol)
        async with lock:
            self.seq_states[symbol] = SeqState(
                last_u=0, epoch=epoch, last_mono_ms=monotonic_ms()
            )

    async def set_last_u(self, symbol: str, last_u: int, mono_ms: int) -> None:
        """Set last_u (or version) after snapshot."""
        lock = self._get_lock(symbol)
        async with lock:
            state = self.seq_states.get(symbol)
            if state is not None:
                self.seq_states[symbol] = SeqState(
                    last_u=last_u, epoch=state.epoch, last_mono_ms=mono_ms
                )
            else:
                self.seq_states[symbol] = SeqState(
                    last_u=last_u, epoch=0, last_mono_ms=mono_ms
                )