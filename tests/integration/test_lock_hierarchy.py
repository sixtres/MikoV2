"""
Lock hierarchy deadlock detection integration tests.
Y-339 canonical, Y-350 emergency.
"""

import threading
import time

import pytest

from src.utils.locks import (
    LOCK_HIERARCHY,
    LockHierarchy,
    HierarchicalLock,
    create_lock,
    validate_lock_order,
)


def test_hierarchy_order_complete():
    assert LockHierarchy.BUFFER < LockHierarchy.FILL
    assert LockHierarchy.FILL < LockHierarchy.SQLITE
    assert LockHierarchy.SQLITE < LockHierarchy.PACER
    assert LockHierarchy.PACER < LockHierarchy.FLUSH
    assert LockHierarchy.FLUSH < LockHierarchy.TELEMETRY
    assert int(LockHierarchy.BUFFER) == 1
    assert int(LockHierarchy.TELEMETRY) == 6
    assert LOCK_HIERARCHY == (
        "buffer_lock",
        "fill_lock",
        "sqlite_lock",
        "pacer_lock",
        "flush_lock",
        "telemetry_lock",
    )


def test_emergency_order_sqlite_pacer_flush():
    # validate_lock_order returns None on success, raises on violation
    assert validate_lock_order([], "sqlite_lock") is None
    assert validate_lock_order(["sqlite_lock"], "pacer_lock") is None
    assert validate_lock_order(["sqlite_lock", "pacer_lock"], "flush_lock") is None


def test_emergency_reverse_order_fatal():
    with pytest.raises(RuntimeError):
        validate_lock_order(["flush_lock"], "sqlite_lock")


def test_buffer_before_fill_ok():
    assert validate_lock_order([], "buffer_lock") is None
    assert validate_lock_order(["buffer_lock"], "fill_lock") is None


def test_sqlite_before_buffer_fatal():
    with pytest.raises(RuntimeError):
        validate_lock_order(["sqlite_lock"], "buffer_lock")


def test_sealed_lock_separate():
    assert "sealed_lock" not in LOCK_HIERARCHY
    all_locks = list(LOCK_HIERARCHY)
    assert validate_lock_order(all_locks, "sealed_lock") is None
    assert validate_lock_order([], "sealed_lock") is None


def test_hierarchical_lock_thread_local_class_level():
    # _thread_local is class-level on HierarchicalLock
    HierarchicalLock._thread_local = threading.local()

    b = HierarchicalLock(LockHierarchy.BUFFER)
    f = HierarchicalLock(LockHierarchy.FILL)

    # Both instances share class-level _thread_local
    assert HierarchicalLock._thread_local is b._thread_local
    assert HierarchicalLock._thread_local is f._thread_local

    b.acquire()
    try:
        held = getattr(HierarchicalLock._thread_local, "held", set())
        assert LockHierarchy.BUFFER in held

        # FILL acquisition sees BUFFER held via shared thread-local
        f.acquire()
        held2 = getattr(HierarchicalLock._thread_local, "held", set())
        assert LockHierarchy.BUFFER in held2
        assert LockHierarchy.FILL in held2
        f.release()
    finally:
        b.release()
        if hasattr(HierarchicalLock._thread_local, "held"):
            HierarchicalLock._thread_local.held = set()


def test_hierarchical_lock_cross_level_deadlock_detect():
    HierarchicalLock._thread_local = threading.local()

    sqlite_lock = HierarchicalLock(LockHierarchy.SQLITE)
    buffer_lock = HierarchicalLock(LockHierarchy.BUFFER)

    sqlite_lock.acquire()
    try:
        with pytest.raises(RuntimeError):
            buffer_lock.acquire()
    finally:
        sqlite_lock.release()
        if hasattr(HierarchicalLock._thread_local, "held"):
            HierarchicalLock._thread_local.held = set()


def test_no_global_state():
    import src.utils.locks as locks_mod

    for name in dir(locks_mod):
        if name.startswith("__"):
            continue
        obj = getattr(locks_mod, name)
        if isinstance(obj, HierarchicalLock):
            raise AssertionError("global HierarchicalLock instance found: %s" % name)


def test_create_lock_buffer_is_rlock():
    lock = create_lock("buffer_lock")
    assert type(lock).__name__ in ("RLock", "_RLock")


def test_create_lock_others_are_asyncio():
    import asyncio

    for name in ("fill_lock", "sqlite_lock", "pacer_lock", "flush_lock", "telemetry_lock"):
        lock = create_lock(name)
        assert isinstance(lock, asyncio.Lock)


def test_create_lock_unknown_fatal():
    with pytest.raises(ValueError):
        create_lock("unknown_lock")


def test_deadlock_simulation_timeout():
    HierarchicalLock._thread_local = threading.local()

    results = []

    def worker_correct():
        b = HierarchicalLock(LockHierarchy.BUFFER)
        f = HierarchicalLock(LockHierarchy.FILL)
        try:
            b.acquire(timeout=1)
            time.sleep(0.05)
            f.acquire(timeout=1)
            results.append("correct_ok")
            f.release()
            b.release()
        except Exception as e:
            results.append("correct_fail %s" % e)
        finally:
            if hasattr(HierarchicalLock._thread_local, "held"):
                HierarchicalLock._thread_local.held = set()

    def worker_reverse():
        s = HierarchicalLock(LockHierarchy.SQLITE)
        b = HierarchicalLock(LockHierarchy.BUFFER)
        try:
            s.acquire(timeout=1)
            time.sleep(0.05)
            try:
                b.acquire(timeout=1)
                results.append("reverse_should_fail_but_ok")
                b.release()
            except RuntimeError:
                results.append("reverse_detected")
            s.release()
        except Exception as e:
            results.append("reverse_fail %s" % e)
        finally:
            if hasattr(HierarchicalLock._thread_local, "held"):
                HierarchicalLock._thread_local.held = set()

    t1 = threading.Thread(target=worker_correct)
    t2 = threading.Thread(target=worker_reverse)

    t1.start()
    t2.start()

    t1.join(timeout=2)
    t2.join(timeout=2)

    assert not t1.is_alive(), "t1 deadlock"
    assert not t2.is_alive(), "t2 deadlock"
    assert "correct_ok" in results, "results: %s" % results
    assert "reverse_detected" in results, "results: %s" % results