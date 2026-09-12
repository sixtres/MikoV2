import asyncio
import time
from pathlib import Path

import pytest

from src.storage.archiver import Archiver, ArchiverConfig

def _make_archiver(tmp_path):
    live = tmp_path / "live"
    arch = tmp_path / "archive"
    live.mkdir(parents=True, exist_ok=True)
    arch.mkdir(parents=True, exist_ok=True)
    cfg = ArchiverConfig(live_dir=live, archive_dir=arch, snappy_level=9, live_days=7, archive_days=365)
    lock = asyncio.Lock()
    archiver = Archiver(cfg, lock)
    return archiver, cfg

def test_config_defaults(tmp_path):
    live = tmp_path / "live"
    arch = tmp_path / "archive"
    cfg = ArchiverConfig(live_dir=live, archive_dir=arch)
    assert cfg.snappy_level == 9
    assert cfg.live_days == 7
    assert cfg.archive_days == 365

def test_constants():
    assert Archiver.ARCHIVE_UTC_HOUR == 0
    assert Archiver.ORPHAN_CLOSED_MS == 300000
    assert Archiver.ORPHAN_DELETED_MS == 3600000
    assert Archiver.DISK_FULL_PCT == 90

@pytest.mark.asyncio
async def test_archive_file_atomic(tmp_path):
    archiver, cfg = _make_archiver(tmp_path)
    try:
        import pandas as pd

        df = pd.DataFrame([{"symbol": "BTCUSDT", "price": 100.0}])
        src = cfg.live_dir / "test.parquet"
        df.to_parquet(str(src))
        dest = await archiver.archive_file(src)
        assert dest.exists()
        assert not src.exists()
        assert (cfg.archive_dir / "test.parquet").exists()
    except ImportError:
        pytest.skip("pandas not available")

@pytest.mark.asyncio
async def test_run_daily(tmp_path):
    archiver, cfg = _make_archiver(tmp_path)
    try:
        import pandas as pd

        df = pd.DataFrame([{"symbol": "BTCUSDT"}])
        old_file = cfg.live_dir / "old.parquet"
        df.to_parquet(str(old_file))
        old = time.time() - 8 * 86400
        import os

        os.utime(old_file, (old, old))
        await archiver.run_daily()
        archived = list(cfg.archive_dir.glob("*.parquet"))
        assert len(archived) >= 1
    except ImportError:
        pytest.skip("pandas not available")

@pytest.mark.asyncio
async def test_trim_old(tmp_path):
    archiver, cfg = _make_archiver(tmp_path)
    try:
        import pandas as pd

        df = pd.DataFrame([{"a": 1}])
        old_file = cfg.archive_dir / "old.parquet"
        df.to_parquet(str(old_file))
        old = time.time() - 400 * 86400
        import os

        os.utime(old_file, (old, old))
        removed = await archiver.trim_old()
        assert removed >= 1
        assert not old_file.exists()
    except ImportError:
        pytest.skip("pandas not available")

@pytest.mark.asyncio
async def test_recover_orphans(tmp_path):
    archiver, cfg = _make_archiver(tmp_path)
    orphan_closed = cfg.live_dir / "x.parquet._closed"
    orphan_closed.write_text("orphan")
    old = time.time() - 400
    import os

    os.utime(orphan_closed, (old, old))
    orphan_del = cfg.archive_dir / "y.parquet.deleted"
    orphan_del.write_text("orphan")
    os.utime(orphan_del, (time.time() - 3700, time.time() - 3700))

    removed = await archiver.recover_orphans()
    assert removed >= 2
    assert not orphan_closed.exists()
    assert not orphan_del.exists()

@pytest.mark.asyncio
async def test_enforce_disk_limit(tmp_path):
    archiver, cfg = _make_archiver(tmp_path)
    removed = await archiver.enforce_disk_limit()
    assert isinstance(removed, int)

def test_no_global_state():
    assert not hasattr(Archiver, "_config") or isinstance(
        getattr(Archiver, "_config", None), property
    )