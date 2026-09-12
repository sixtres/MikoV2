import asyncio
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.storage.orderbook_store import OrderBookStore, OrderBookStoreConfig

def _make_store(tmp_path, suspended=0):
    live = tmp_path / "live"
    archive = tmp_path / "archive"
    live.mkdir(parents=True, exist_ok=True)
    archive.mkdir(parents=True, exist_ok=True)
    cfg = OrderBookStoreConfig(
        live_dir=live,
        archive_dir=archive,
        live_days=7,
        archive_days=365,
        batch_size=5,
        flush_threshold=10,
        snappy_live=1,
        snappy_archive=9,
    )
    write_lock = asyncio.Lock()
    read_lock = threading.RLock()
    flush_counter = MagicMock()
    flush_counter._counter = suspended
    store = OrderBookStore(cfg, write_lock, read_lock, flush_counter)
    return store, cfg

def test_config_defaults(tmp_path):
    live = tmp_path / "live"
    arch = tmp_path / "archive"
    cfg = OrderBookStoreConfig(live_dir=live, archive_dir=arch)
    assert cfg.live_days == 7
    assert cfg.archive_days == 365
    assert cfg.batch_size == 500
    assert cfg.flush_threshold == 5000
    assert cfg.snappy_live == 1
    assert cfg.snappy_archive == 9

def test_constants():
    assert OrderBookStore.ORPHAN_CLOSED_MS == 300000
    assert OrderBookStore.ORPHAN_DELETED_MS == 3600000
    assert OrderBookStore.DISK_FULL_PCT == 90

@pytest.mark.asyncio
async def test_append_and_flush(tmp_path):
    store, cfg = _make_store(tmp_path)
    await store.append({"symbol": "BTCUSDT", "ts_ms": int(time.time() * 1000), "price": 100.0})
    assert len(store._buffer) == 1
    n = await store.flush()
    assert n == 1
    assert len(store._buffer) == 0
    files = list(cfg.live_dir.glob("*.parquet"))
    assert len(files) == 1

@pytest.mark.asyncio
async def test_batch_flush_auto(tmp_path):
    store, cfg = _make_store(tmp_path)
    cfg = store._config
    # batch_size=5
    for i in range(5):
        await store.append({"symbol": "BTCUSDT", "ts_ms": int(time.time() * 1000) + i, "price": float(i)})
    # after 5 append, auto flush should have happened
    files = list(cfg.live_dir.glob("*.parquet"))
    assert len(files) >= 1

@pytest.mark.asyncio
async def test_append_suspended_drop(tmp_path):
    store, cfg = _make_store(tmp_path, suspended=1)
    await store.append({"symbol": "BTCUSDT", "ts_ms": int(time.time() * 1000)})
    assert len(store._buffer) == 0

@pytest.mark.asyncio
async def test_rotate_orphan_closed(tmp_path):
    store, cfg = _make_store(tmp_path)
    orphan = cfg.live_dir / "test.parquet._closed"
    orphan.write_text("orphan")
    # make old mtime
    old = time.time() - 400
    import os

    os.utime(orphan, (old, old))
    await store.rotate()
    assert not orphan.exists()

@pytest.mark.asyncio
async def test_rotate_orphan_deleted(tmp_path):
    store, cfg = _make_store(tmp_path)
    orphan = cfg.live_dir / "test.parquet.deleted"
    orphan.write_text("orphan")
    old = time.time() - 3700
    import os

    os.utime(orphan, (old, old))
    await store.rotate()
    assert not orphan.exists()

@pytest.mark.asyncio
async def test_archive_task(tmp_path):
    store, cfg = _make_store(tmp_path)
    # create old parquet file
    try:
        import pandas as pd

        df = pd.DataFrame([{"symbol": "BTCUSDT", "ts_ms": 1}])
        old_file = cfg.live_dir / "old.parquet"
        df.to_parquet(str(old_file))
        old = time.time() - 8 * 86400
        import os

        os.utime(old_file, (old, old))
        await store.archive_task()
        archived = list(cfg.archive_dir.glob("*.parquet"))
        assert len(archived) >= 1
    except ImportError:
        pytest.skip("pandas not available")

@pytest.mark.asyncio
async def test_enforce_disk_limit(tmp_path):
    store, cfg = _make_store(tmp_path)
    # enforce should return int and not crash when disk not full
    removed = await store.enforce_disk_limit()
    assert isinstance(removed, int)

def test_read_snapshot(tmp_path):
    store, cfg = _make_store(tmp_path)
    result = store.read_snapshot("BTCUSDT", 0, int(time.time() * 1000))
    # should return DataFrame or list
    assert result is not None

def test_no_global_state():
    assert not hasattr(OrderBookStore, "_buffer")