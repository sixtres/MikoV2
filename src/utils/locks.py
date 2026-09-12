# YAMA Y-253: buffer_lock SINGLE RLock (reentrant apply_batch->trim)
# YAMA Y-265: sealed_lock ayri (fill_lock'tan)
# YAMA Y-339: lock hierarchy buffer>fill>sqlite>pacer>flush>telemetry, CI assert reentrant owner check
# YAMA Y-350: emergency sqlite(3)->pacer(4)->flush(5)
# YAMA Y-358: threading.Lock YASAK (istisna buffer_lock)

"""
Lock hierarchy and factories.

Y-253: buffer_lock single RLock for reentrant apply_batch->trim.
Y-265: sealed_lock separate from fill_lock.
Y-339: hierarchy BUFFER(1)<FILL(2)<SQLITE(3)<PACER(4)<FLUSH(5)<TELEMETRY(6), reentrant owner check via thread-local.
Y-350: emergency path sqlite->pacer->flush (3->4->5).
Y-358: threading.Lock forbidden except buffer_lock RLock special case.
"""

from __future__ import annotations

import asyncio
import threading
from enum import IntEnum
from typing import Final, Union

class LockHierarchy(IntEnum):
    BUFFER = 1
    FILL = 2
    SQLITE = 3
    PACER = 4
    FLUSH = 5
    TELEMETRY = 6

SEALED_LOCK_NAME: Final[str] = "sealed_lock"

LOCK_HIERARCHY: Final[tuple[str,...]] = (
    "buffer_lock",
    "fill_lock",
    "sqlite_lock",
    "pacer_lock",
    "flush_lock",
    "telemetry_lock",
)

_NAME_TO_LEVEL: dict[str, LockHierarchy] = {
    "buffer_lock": LockHierarchy.BUFFER,
    "fill_lock": LockHierarchy.FILL,
    "sqlite_lock": LockHierarchy.SQLITE,
    "pacer_lock": LockHierarchy.PACER,
    "flush_lock": LockHierarchy.FLUSH,
    "telemetry_lock": LockHierarchy.TELEMETRY,
}

class HierarchicalLock:
    """
    Hierarchical lock with thread-local owner tracking.

    Y-339: CI assert reentrant owner check.
    _thread_local must be class-level (critical bug if instance-level).
    """

    _thread_local = threading.local()

    def __init__(self, level: LockHierarchy) -> None:
        self.level: LockHierarchy = level
        self._lock = threading.Lock()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        """
        Acquire with hierarchy check.

        - held = getattr(_thread_local, "held", set())
        - for lvl in held: if lvl >= self.level: raise RuntimeError
        - on success add level to held
        """
        held = getattr(self._thread_local, "held", set())
        for lvl in held:
            if lvl >= self.level:
                raise RuntimeError(
                    f"FATAL: lock order violation: held {lvl} >= requested {self.level}"
                )

        success = self._lock.acquire(blocking, timeout)

        if success:
            if not hasattr(self._thread_local, "held"):
                self._thread_local.held = set()
            self._thread_local.held.add(self.level)

        return success

    def release(self) -> None:
        """Release and discard from thread-local."""
        self._lock.release()
        held = getattr(self._thread_local, "held", None)
        if held is not None:
            held.discard(self.level)

    def __enter__(self) -> "HierarchicalLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.release()
        return False

def create_lock(name: str) -> Union[asyncio.Lock, threading.RLock]:
    """
    Factory for locks.

    Y-253: buffer_lock SINGLE RLock (reentrant)
    Y-265: sealed_lock separate -> asyncio.Lock
    Y-358: threading.Lock forbidden, only RLock for buffer_lock
    """
    if name == "buffer_lock":
        return threading.RLock()

    if name == SEALED_LOCK_NAME:
        return asyncio.Lock()

    if name in LOCK_HIERARCHY:
        return asyncio.Lock()

    raise ValueError(f"FATAL: unknown lock name: {name}")

def validate_lock_order(acquired: list[str], next_lock: str) -> None:
    """
    Validate next_lock against already acquired locks.

    - next_lock must be in LOCK_HIERARCHY or sealed_lock
    - sealed_lock independent from main hierarchy
    - order must be strictly increasing
    - violation -> RuntimeError
    """
    if next_lock == SEALED_LOCK_NAME:
        return

    if next_lock not in LOCK_HIERARCHY:
        raise ValueError(f"FATAL: unknown next_lock: {next_lock}")

    next_level = _NAME_TO_LEVEL.get(next_lock)
    if next_level is None:
        raise ValueError(f"FATAL: no level mapping for {next_lock}")

    max_level: LockHierarchy | None = None
    for name in acquired:
        if name == SEALED_LOCK_NAME:
            continue
        if name not in LOCK_HIERARCHY:
            raise ValueError(f"FATAL: unknown acquired lock: {name}")
        lvl = _NAME_TO_LEVEL[name]
        if max_level is None or lvl > max_level:
            max_level = lvl

    if max_level is not None and next_level <= max_level:
        raise RuntimeError(
            f"FATAL: lock order violation: acquired max {max_level} >= next {next_level} ({next_lock})"
        )

def is_asyncio_lock(lock: object) -> bool:
    """
    Check lock type.

    Y-358: threading.Lock forbidden -> FATAL ValueError
    - asyncio.Lock -> True
    - threading.RLock (type name _RLock) -> False
    - threading.Lock (type name lock) -> ValueError
    """
    if isinstance(lock, asyncio.Lock):
        return True
    name = type(lock).__name__
    if name == "_RLock":
        return False
    if name == "lock":
        raise ValueError("FATAL: threading.Lock YASAK, use RLock for buffer_lock or asyncio.Lock")
    return False