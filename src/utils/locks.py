# YAMA Y-358: asyncio.Lock only except buffer_lock RLock per Y-253 (reentrant apply_batch->trim)
# YAMA Y-339: Lock hierarchy buffer>fill>sqlite>pacer>flush>telemetry - sealed_lock separate not in main hierarchy (Y-265, Y-340)
# YAMA Y-339 leaf locks: token_bucket, _state_sem, _seq_lock (not in main hierarchy, no deadlock risk against main sequence)
# YAMA Y-353: Stateless factory - no global mutable lock instances

"""
Locks utils.

Provides lock factory with hierarchy validation.
- buffer_lock uses RLock per Y-253 (reentrant needed by apply_batch->trim)
- All other locks are asyncio.Lock (Y-358)
- Lock hierarchy enforced (Y-339): buffer>fill>sqlite>pacer>flush>telemetry
- sealed_lock is separate, not in main hierarchy (Y-265, Y-340), scalar not dict guard
- Leaf locks token_bucket, _state_sem, _seq_lock not in main hierarchy
"""

from __future__ import annotations

import asyncio
import threading
from typing import Final

# AnaYasa lock hierarchy order (lower index = higher priority, must acquire first)
# 6 elements - sealed_lock separate
LOCK_HIERARCHY: Final[tuple[str,...]] = (
    "buffer_lock",
    "fill_lock",
    "sqlite_lock",
    "pacer_lock",
    "flush_lock",
    "telemetry_lock",
)

SEALED_LOCK_NAME: Final[str] = "sealed_lock"

def create_lock(name: str) -> asyncio.Lock | threading.RLock:
    """
    Create lock with hierarchy name.

    buffer_lock uses RLock per Y-253 (reentrant needed by apply_batch->trim).
    All other locks are asyncio.Lock (Y-358).
    """
    raise NotImplementedError("FAZ 1")

def validate_lock_order(acquired: list[str], next_lock: str) -> None:
    """
    Validate lock acquisition order against hierarchy (Y-339).

    FATAL if order reversed.
    sealed_lock is separate, not in main hierarchy (Y-265, Y-340).
    """
    raise NotImplementedError("FAZ 1")

def is_asyncio_lock(lock: object) -> bool:
    """Check if lock is asyncio.Lock - FATAL if threading.Lock except buffer_lock RLock."""
    raise NotImplementedError("FAZ 1")