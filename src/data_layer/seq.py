# YAMA Y-254: Sequence gap detection, epoch reset on reconnect, same lock pre_sync_queue clear
# YAMA Y-313: on_snapshot seq_epoch single increment
# YAMA Y-314: per-symbol seq_epoch defaultdict reset on reconnect
# YAMA Y-353: Stateless - no global mutable, per-symbol state via DI dict
# YAMA Y-358: asyncio.Lock for seq state

"""
Sequence validation.

Validates Binance-like L2 stream sequence with epoch support:
- u = final update ID, U = first update ID (or pu/u)
- epoch check: mismatch -> invalid + needs_resync
- Gap if current U > last_u + 1 -> trigger re-sync
- Monotonic check last_u < u
- Per-symbol state via DI dict, no global
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SeqState:
    last_u: int
    epoch: int
    last_mono_ms: int # Monotonic clock for stale detection - wall clock not used (Y-353).

@dataclass(frozen=True, slots=True)
class SeqResult:
    is_valid: bool
    is_gap: bool
    needs_resync: bool
    last_u: int

class SequenceValidator:
    """
    Per-symbol sequence validator.

    State held in external dict (DI), no global mutable.
    Uses asyncio.Lock (Y-358) for _seq_lock.
    """

    def __init__(
        self, seq_states: dict[str, SeqState], seq_locks: dict[str, asyncio.Lock]
    ) -> None:
        self._seq_states = seq_states
        self._seq_locks = seq_locks

    async def get_state(self, symbol: str) -> SeqState | None:
        raise NotImplementedError("FAZ 2")

    async def validate(
        self, symbol: str, epoch: int, first_u: int, final_u: int
    ) -> SeqResult:
        """
        Validate sequence with epoch check (Y-254).

        If epoch != state.epoch: return invalid, needs_resync=True.
        If first_u > last_u + 1: gap -> needs_resync=True.
        If final_u <= last_u: stale -> drop, needs_resync=False.
        Otherwise valid, update last_u.
        """
        raise NotImplementedError("FAZ 2")

    async def reset(self, symbol: str) -> None:
        """Reset sequence state on re-sync."""
        raise NotImplementedError("FAZ 2")

    async def set_epoch(self, symbol: str, epoch: int) -> None:
        """Set epoch on reconnect, resets last_u to 0."""
        raise NotImplementedError("FAZ 2")

    async def set_last_u(self, symbol: str, last_u: int, mono_ms: int) -> None:
        """Set last_u after snapshot sync."""
        raise NotImplementedError("FAZ 2")