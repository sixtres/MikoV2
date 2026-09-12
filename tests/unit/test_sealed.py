import asyncio
import time
from unittest.mock import patch

import pytest

from src.storage.sealed import SealedStore, SealedStoreConfig

def _make_store():
    lock = asyncio.Lock()
    cfg = SealedStoreConfig()
    return SealedStore(cfg, lock), lock

def test_config_defaults():
    cfg = SealedStoreConfig()
    assert cfg.seal_ttl_ms == 300000
    assert cfg.exchange_ts_tolerance_ms == 2000

@pytest.mark.asyncio
async def test_seal_inserts_entry():
    store, _ = _make_store()
    await store.seal("oid1", 1000, 1000, 1)
    assert store.size() == 1

@pytest.mark.asyncio
async def test_seal_overwrites_existing():
    store, _ = _make_store()
    await store.seal("oid1", 1000, 1000, 1)
    await store.seal("oid1", 2000, 2000, 2)
    assert store.size() == 1

@pytest.mark.asyncio
async def test_is_sealed_true_after_seal():
    store, _ = _make_store()
    await store.seal("oid1", 1000, 1000, 1)
    assert await store.is_sealed("oid1", 1500) is True

@pytest.mark.asyncio
async def test_is_sealed_false_if_not_sealed():
    store, _ = _make_store()
    assert await store.is_sealed("oid1", 1500) is False

@pytest.mark.asyncio
async def test_is_sealed_exchange_ts_none_guard():
    store, _ = _make_store()
    await store.seal("oid1", 1000, None, 1)
    assert await store.is_sealed("oid1", 1500) is True

@pytest.mark.asyncio
async def test_is_sealed_old_event_returns_true():
    store, _ = _make_store()
    await store.seal("oid1", 5000, 5000, 1)
    # incoming < exch_ts - 2000 => old event
    assert await store.is_sealed("oid1", 1000) is True

@pytest.mark.asyncio
async def test_cleanup_expired_local():
    store, _ = _make_store()
    now = int(time.time() * 1000)
    await store.seal("oid1", now - 400_000, None, 1)
    removed = await store.cleanup_expired()
    assert removed == 1
    assert store.size() == 0

@pytest.mark.asyncio
async def test_cleanup_expired_exchange():
    store, _ = _make_store()
    now = int(time.time() * 1000)
    await store.seal("oid1", now, now - 400_000, 1)
    removed = await store.cleanup_expired()
    assert removed == 1
    assert store.size() == 0

@pytest.mark.asyncio
async def test_cleanup_full_scan_no_break():
    store, _ = _make_store()
    now = int(time.time() * 1000)
    # first not expired, second expired, third not expired
    await store.seal("a", now, None, 1)
    await store.seal("b", now - 400_000, None, 1)
    await store.seal("c", now, None, 1)
    removed = await store.cleanup_expired()
    assert removed == 1
    assert store.size() == 2
    assert "b" not in store._sealed_orders

@pytest.mark.asyncio
async def test_cleanup_returns_count():
    store, _ = _make_store()
    now = int(time.time() * 1000)
    await store.seal("a", now - 400_000, None, 1)
    await store.seal("b", now - 400_000, None, 1)
    removed = await store.cleanup_expired()
    assert removed == 2

@pytest.mark.asyncio
async def test_size_after_seal():
    store, _ = _make_store()
    await store.seal("a", 0, 0, 1)
    await store.seal("b", 0, 0, 1)
    assert store.size() == 2

@pytest.mark.asyncio
async def test_clear_empties():
    store, _ = _make_store()
    await store.seal("a", 0, 0, 1)
    store.clear()
    assert store.size() == 0

def test_no_global_state():
    assert not hasattr(SealedStore, "_sealed_orders")