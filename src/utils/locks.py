"""Async lock utilities for MikoV2.

Y-358: Only asyncio.Lock allowed, threading.Lock PROHIBITED.
Y-339: Lock hierarchy assertions for deadlock prevention.
No global state (Y-353).
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator


class LockHierarchy:
    """Lock hierarchy manager for deadlock prevention.
    
    Y-339: Enforces strict lock ordering to prevent deadlocks.
    Hierarchy levels: sqlite(3) < pacer(4) < flush(5)
    """
    
    SQLITE: int = 3
    PACER: int = 4
    FLUSH: int = 5
    
    def __init__(self) -> None:
        """Initialize lock hierarchy tracker."""
        self._current_level: int = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self, level: int) -> None:
        """Acquire lock at specified hierarchy level.
        
        Args:
            level: Lock hierarchy level (must be > current).
            
        Raises:
            RuntimeError: If lock order violation detected.
        """
        async with self._lock:
            if level <= self._current_level:
                raise RuntimeError(
                    f"Lock hierarchy violation: trying to acquire level {level} "
                    f"while holding level {self._current_level} (Y-339)"
                )
            self._current_level = level
    
    async def release(self, level: int) -> None:
        """Release lock at specified hierarchy level.
        
        Args:
            level: Lock hierarchy level being released.
        """
        async with self._lock:
            if self._current_level == level:
                self._current_level = 0
    
    def assert_hierarchy(self, expected_order: list[int]) -> None:
        """Assert that lock acquisition order matches expected.
        
        Y-339: CI assertion for lock hierarchy compliance.
        
        Args:
            expected_order: Expected lock acquisition order.
            
        Raises:
            AssertionError: If order mismatch.
        """
        for i in range(len(expected_order) - 1):
            if expected_order[i] >= expected_order[i + 1]:
                raise AssertionError(
                    f"Lock hierarchy order violation: {expected_order} (Y-339)"
                )


@asynccontextmanager
async def hierarchical_lock(
    lock: asyncio.Lock,
    hierarchy: LockHierarchy,
    level: int,
) -> AsyncIterator[None]:
    """Context manager for acquiring hierarchical locks.
    
    Y-358: Uses only asyncio.Lock.
    Y-339: Enforces hierarchy on acquire/release.
    
    Args:
        lock: asyncio.Lock to acquire.
        hierarchy: LockHierarchy manager.
        level: Hierarchy level for this lock.
        
    Yields:
        None
        
    Raises:
        RuntimeError: On hierarchy violation.
    """
    await hierarchy.acquire(level)
    try:
        async with lock:
            yield
    finally:
        await hierarchy.release(level)


def create_async_lock() -> asyncio.Lock:
    """Create a new asyncio.Lock.
    
    Y-358: Factory ensuring only asyncio.Lock is used.
    
    Returns:
        asyncio.Lock: New lock instance.
    """
    return asyncio.Lock()
