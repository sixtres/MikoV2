# YAMA Y-254: epoch reset on reconnect, same lock pre_sync_queue clear
# YAMA Y-313: seq_epoch single increment
# YAMA Y-314: per-symbol seq_epoch defaultdict reset on reconnect
# YAMA Y-358: asyncio.Lock

"""
Sequence validator - per-symbol orderbook update sequencing.

Y-254: epoch reset on reconnect.
Y-313: seq_epoch single increment.
Y-314: per-symbol seq_epoch reset on reconnect.
Y-358: asyncio.Lock.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from ..utils.time import monotonic_ms

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
    seq_locks: dict[symbol, asyncio.Lock]
    """

    def __init__(self, seq_states: dict, seq_locks: dict) -> None:
        self.seq_states = seq_states
        self.seq_locks = seq_locks

    async def get_state(self, symbol: str) -> SeqState | None:
        """Return state or None."""
        return self.seq_states.get(symbol)

    async def validate(
        self,
        symbol: str,
        epoch: int,
        first_u: int,
        final_u: int,
    ) -> SeqResult:
        """
        Validate update.

        - no state -> needs_resync=True
        - epoch mismatch -> needs_resync=True
        - final_u <= last_u -> stale drop, invalid no resync
        - first_u > last_u+1 -> gap, needs_resync=True
        - else valid and update state
        """
        lock = self.seq_locks.get(symbol)
        if lock is None:
            lock = asyncio.Lock()
            self.seq_locks[symbol] = lock

        async with lock:
            state = self.seq_states.get(symbol)

            if state is None:
                return SeqResult(
                    is_valid=False, is_gap=False, needs_resync=True, last_u=0
                )

            if epoch!= state.epoch:
                return SeqResult(
                    is_valid=False,
                    is_gap=False,
                    needs_resync=True,
                    last_u=state.last_u,
                )

            if final_u <= state.last_u:
                # stale drop
                return SeqResult(
                    is_valid=False,
                    is_gap=False,
                    needs_resync=False,
                    last_u=state.last_u,
                )

            if first_u > state.last_u + 1:
                return SeqResult(
                    is_valid=False,
                    is_gap=True,
                    needs_resync=True,
                    last_u=state.last_u,
                )

            # valid
            new_state = SeqState(
                last_u=final_u,
                epoch=epoch,
                last_mono_ms=monotonic_ms(),
            )
            self.seq_states[symbol] = new_state
            return SeqResult(
                is_valid=True, is_gap=False, needs_resync=False, last_u=final_u
            )

    async def reset(self, symbol: str) -> None:
        """Remove state and lock."""
        lock = self.seq_locks.get(symbol)
        if lock is not None:
            async with lock:
                self.seq_states.pop(symbol, None)
        self.seq_states.pop(symbol, None)
        self.seq_locks.pop(symbol, None)

    async def set_epoch(self, symbol: str, epoch: int) -> None:
        """
        Set new epoch, reset last_u to 0.

        Y-254: epoch reset on reconnect.
        Y-314: per-symbol reset.
        """
        lock = self.seq_locks.get(symbol)
        if lock is None:
            lock = asyncio.Lock()
            self.seq_locks[symbol] = lock

        async with lock:
            self.seq_states[symbol] = SeqState(
                last_u=0, epoch=epoch, last_mono_ms=monotonic_ms()
            )

    async def set_last_u(self, symbol: str, last_u: int, mono_ms: int) -> None:
        """Set last_u after snapshot."""
        lock = self.seq_locks.get(symbol)
        if lock is None:
            lock = asyncio.Lock()
            self.seq_locks[symbol] = lock

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