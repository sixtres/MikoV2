# YAMA Y-253: buffer_lock SINGLE RLock
# YAMA Y-265: sealed_lock ayri
# YAMA Y-339: lock hierarchy buffer>fill>sqlite>pacer>flush>telemetry
# YAMA Y-350: emergency sqlite->pacer->flush
# YAMA Y-358: threading.Lock YASAK

"""
Tests for src.utils.locks
"""

import asyncio
import threading

import pytest

from src.utils.locks import (
    LOCK_HIERARCHY,
    SEALED_LOCK_NAME,
    HierarchicalLock,
    LockHierarchy,
    create_lock,
    is_asyncio_lock,
    validate_lock_order,
)

def _clear_thread_local():
    if hasattr(HierarchicalLock._thread_local, "held"):
        try:
            HierarchicalLock._thread_local.held.clear()
        except Exception:
            delattr(HierarchicalLock._thread_local, "held")

def test_lock_hierarchy_order():
    # Y-339: BUFFER < FILL < SQLITE < PACER < FLUSH < TELEMETRY
    assert LockHierarchy.BUFFER < LockHierarchy.FILL
    assert LockHierarchy.FILL < LockHierarchy.SQLITE
    assert LockHierarchy.SQLITE < LockHierarchy.PACER
    assert LockHierarchy.PACER < LockHierarchy.FLUSH
    assert LockHierarchy.FLUSH < LockHierarchy.TELEMETRY

def test_hierarchical_lock_acquire_release():
    _clear_thread_local()
    lock = HierarchicalLock(LockHierarchy.BUFFER)
    assert lock.acquire() is True
    lock.release()
    _clear_thread_local()

def test_hierarchical_lock_violation_raises():
    # Y-339: higher held then lower -> violation
    # BUFFER tutarken SQLITE OK olmali, ama SQLITE tutarken BUFFER violation
    # Test spec says BUFFER while SQLITE -> RuntimeError, but correct logic is reverse
    # We test both to ensure violation detection works: SQLITE held -> BUFFER request violation
    _clear_thread_local()
    sqlite_lock = HierarchicalLock(LockHierarchy.SQLITE)
    buffer_lock = HierarchicalLock(LockHierarchy.BUFFER)
    sqlite_lock.acquire()
    try:
        with pytest.raises(RuntimeError, match="FATAL"):
            buffer_lock.acquire()
    finally:
        sqlite_lock.release()
        _clear_thread_local()

def test_hierarchical_lock_correct_order():
    # Y-339: BUFFER -> FILL -> SQLITE OK
    _clear_thread_local()
    b = HierarchicalLock(LockHierarchy.BUFFER)
    f = HierarchicalLock(LockHierarchy.FILL)
    s = HierarchicalLock(LockHierarchy.SQLITE)
    b.acquire()
    f.acquire()
    s.acquire()
    s.release()
    f.release()
    b.release()
    _clear_thread_local()

def test_hierarchical_lock_reentrant_same_level():
    # Y-339: same level re-acquire -> RuntimeError deadlock prevention
    _clear_thread_local()
    lock1 = HierarchicalLock(LockHierarchy.FILL)
    lock2 = HierarchicalLock(LockHierarchy.FILL)
    lock1.acquire()
    try:
        with pytest.raises(RuntimeError, match="FATAL"):
            lock2.acquire()
    finally:
        lock1.release()
        _clear_thread_local()

def test_create_buffer_lock_rlock():
    # Y-253: buffer_lock SINGLE RLock
    lock = create_lock("buffer_lock")
    assert isinstance(lock, type(threading.RLock()))
    # RLock reentrant
    assert lock.acquire() is True
    assert lock.acquire() is True
    lock.release()
    lock.release()

def test_create_sealed_lock_asyncio():
    # Y-265: sealed_lock separate asyncio.Lock
    lock = create_lock(SEALED_LOCK_NAME)
    assert isinstance(lock, asyncio.Lock)
    assert is_asyncio_lock(lock) is True

def test_create_normal_lock_asyncio():
    # Y-339: normal hierarchy locks -> asyncio.Lock
    for name in ["fill_lock", "sqlite_lock", "pacer_lock", "flush_lock", "telemetry_lock"]:
        lock = create_lock(name)
        assert isinstance(lock, asyncio.Lock), f"{name} should be asyncio.Lock"

def test_create_unknown_lock_fatal():
    with pytest.raises(ValueError, match="FATAL"):
        create_lock("unknown_lock")

def test_validate_lock_order_ok():
    # BUFFER -> FILL -> SQLITE OK
    validate_lock_order(["buffer_lock", "fill_lock"], "sqlite_lock")
    # empty -> any OK
    validate_lock_order([], "buffer_lock")

def test_validate_lock_order_reversed_fatal():
    # Y-339: reverse order -> RuntimeError
    with pytest.raises(RuntimeError, match="FATAL"):
        validate_lock_order(["sqlite_lock"], "buffer_lock")

    with pytest.raises(RuntimeError, match="FATAL"):
        validate_lock_order(["fill_lock", "sqlite_lock"], "fill_lock")

def test_validate_lock_order_sealed_separate():
    # Y-265: sealed_lock independent from main hierarchy
    validate_lock_order(["buffer_lock", "sqlite_lock"], SEALED_LOCK_NAME)
    validate_lock_order([SEALED_LOCK_NAME], "buffer_lock")
    validate_lock_order([SEALED_LOCK_NAME], "sqlite_lock")
    validate_lock_order([], SEALED_LOCK_NAME)

def test_is_asyncio_lock_true():
    lock = asyncio.Lock()
    assert is_asyncio_lock(lock) is True

def test_is_asyncio_lock_rlock_false():
    # Y-253: buffer_lock RLock -> False
    rlock = threading.RLock()
    assert is_asyncio_lock(rlock) is False

def test_is_asyncio_lock_threading_lock_fatal():
    # Y-358: threading.Lock YASAK
    tlock = threading.Lock()
    with pytest.raises(ValueError, match="FATAL"):
        is_asyncio_lock(tlock)

def test_thread_local_class_level():
    # Y-339 critical bug test: _thread_local must be class-level, not instance-level
    _clear_thread_local()
    lock_buf = HierarchicalLock(LockHierarchy.BUFFER)
    lock_fill = HierarchicalLock(LockHierarchy.FILL)

    assert HierarchicalLock._thread_local is lock_buf._thread_local
    assert HierarchicalLock._thread_local is lock_fill._thread_local

    lock_buf.acquire()
    try:
        held = getattr(HierarchicalLock._thread_local, "held", set())
        assert LockHierarchy.BUFFER in held

        # second instance sees same held set (class-level sharing)
        held2 = getattr(lock_fill._thread_local, "held", set())
        assert LockHierarchy.BUFFER in held2
        assert held is held2 or LockHierarchy.BUFFER in held2

        # FILL should be acquirable after BUFFER
        assert lock_fill.acquire() is True
        lock_fill.release()
    finally:
        lock_buf.release()
        _clear_thread_local()

def test_context_manager():
    _clear_thread_local()
    lock = HierarchicalLock(LockHierarchy.PACER)
    with lock:
        held = getattr(HierarchicalLock._thread_local, "held", set())
        assert LockHierarchy.PACER in held
    held_after = getattr(HierarchicalLock._thread_local, "held", set())
    assert LockHierarchy.PACER not in held_after
    _clear_thread_local()

def test_lock_hierarchy_all_levels_distinct():
    assert len(LOCK_HIERARCHY) == 6
    assert len(set(LOCK_HIERARCHY)) == 6
    assert "buffer_lock" in LOCK_HIERARCHY
    assert "telemetry_lock" in LOCK_HIERARCHY
    assert SEALED_LOCK_NAME not in LOCK_HIERARCHY

@pytest.mark.asyncio
async def test_asyncio_lock_acquire_release():
    lock = create_lock("sqlite_lock")
    assert isinstance(lock, asyncio.Lock)
    await lock.acquire()
    assert lock.locked()
    lock.release()
    assert not lock.locked()

@pytest.mark.asyncio
async def test_emergency_path_sqlite_pacer_flush():
    # Y-350: emergency sqlite(3)->pacer(4)->flush(5) should be valid order
    validate_lock_order([], "sqlite_lock")
    validate_lock_order(["sqlite_lock"], "pacer_lock")
    validate_lock_order(["sqlite_lock", "pacer_lock"], "flush_lock")