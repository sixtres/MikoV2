# YAMA Y-331: UTC 00:00 daily task ayri
# YAMA Y-353: DI
# YAMA Y-358: rotation_lock asyncio.Lock DI
# YAMA Y-269: _ms int whitelist

"""
Daily Parquet archiver - 00:00 UTC daily, atomic tmp->rename, orphan recovery.

Y-331: UTC 00:00 daily task ayri.
Y-353: DI no global.
Y-358: rotation_lock asyncio.Lock DI.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import pandas as pd
except Exception:
    pd = None

@dataclass(frozen=True, slots=True)
class ArchiverConfig:
    live_dir: Path
    archive_dir: Path
    snappy_level: int = 9
    live_days: int = 7
    archive_days: int = 365

class Archiver:
    ARCHIVE_UTC_HOUR = 0
    ORPHAN_CLOSED_MS = 300000
    ORPHAN_DELETED_MS = 3600000
    DISK_FULL_PCT = 90

    def __init__(self, config: ArchiverConfig, rotation_lock: asyncio.Lock) -> None:
        self._config = config
        self._rotation_lock = rotation_lock
        config.live_dir.mkdir(parents=True, exist_ok=True)
        config.archive_dir.mkdir(parents=True, exist_ok=True)

    async def run_daily(self) -> None:
        def _run_sync(cfg: ArchiverConfig) -> None:
            now_s = time.time()
            cutoff_s = now_s - cfg.live_days * 86400
            live_dir = cfg.live_dir
            archive_dir = cfg.archive_dir
            archive_dir.mkdir(parents=True, exist_ok=True)
            for p in live_dir.glob("*.parquet"):
                try:
                    if p.stat().st_mtime < cutoff_s:
                        dest = archive_dir / p.name
                        tmp_dest = archive_dir / (p.name + ".tmp")
                        if pd is not None:
                            try:
                                df = pd.read_parquet(str(p))
                                df.to_parquet(str(tmp_dest), compression="snappy")
                                tmp_dest.rename(dest)
                                p.unlink()
                            except Exception:
                                p.rename(dest)
                        else:
                            p.rename(dest)
                        logger.warning("daily archived %s", p.name)
                except Exception as e:
                    logger.warning("run_daily failed %s: %s", p, e)

        async with self._rotation_lock:
            await asyncio.to_thread(_run_sync, self._config)

    async def archive_file(self, file_path: Path) -> Path:
        def _archive_sync(src: Path, cfg: ArchiverConfig) -> Path:
            dest = cfg.archive_dir / src.name
            tmp_dest = cfg.archive_dir / (src.name + ".tmp")
            try:
                if pd is not None and src.exists():
                    try:
                        df = pd.read_parquet(str(src))
                        df.to_parquet(str(tmp_dest), compression="snappy")
                        tmp_dest.rename(dest)
                        src.unlink()
                    except Exception:
                        # fallback atomic move
                        src.rename(dest)
                else:
                    if src.exists():
                        src.rename(dest)
                logger.warning("archive_file %s -> %s", src.name, dest)
                return dest
            except Exception as e:
                logger.warning("archive_file failed %s: %s", src, e)
                raise

        async with self._rotation_lock:
            return await asyncio.to_thread(_archive_sync, file_path, self._config)

    async def trim_old(self) -> int:
        def _trim_sync(cfg: ArchiverConfig) -> int:
            now_s = time.time()
            cutoff_s = now_s - cfg.archive_days * 86400
            removed = 0
            for p in cfg.archive_dir.glob("*.parquet"):
                try:
                    if p.stat().st_mtime < cutoff_s:
                        p.unlink()
                        removed += 1
                        logger.warning("trim_old removed %s", p.name)
                except Exception as e:
                    logger.warning("trim_old failed %s: %s", p, e)
            return removed

        async with self._rotation_lock:
            return await asyncio.to_thread(_trim_sync, self._config)

    async def recover_orphans(self) -> int:
        def _recover_sync(cfg: ArchiverConfig) -> int:
            now_ms = int(time.time() * 1000)
            removed = 0
            for d in (cfg.live_dir, cfg.archive_dir):
                # Phase 1 ._closed 5m
                for p in d.glob("*.parquet._closed"):
                    try:
                        mtime_ms = int(p.stat().st_mtime * 1000)
                        if now_ms - mtime_ms > Archiver.ORPHAN_CLOSED_MS:
                            p.unlink()
                            removed += 1
                            logger.warning("orphan _closed recovered %s", p.name)
                    except Exception as e:
                        logger.warning("recover _closed failed %s: %s", p, e)
                # Phase 2 .deleted 1h
                for p in d.glob("*.parquet.deleted"):
                    try:
                        mtime_ms = int(p.stat().st_mtime * 1000)
                        if now_ms - mtime_ms > Archiver.ORPHAN_DELETED_MS:
                            p.unlink()
                            removed += 1
                            logger.warning("orphan deleted recovered %s", p.name)
                    except Exception as e:
                        logger.warning("recover deleted failed %s: %s", p, e)
            return removed

        async with self._rotation_lock:
            return await asyncio.to_thread(_recover_sync, self._config)

    async def enforce_disk_limit(self) -> int:
        def _enforce_sync(cfg: ArchiverConfig) -> int:
            try:
                usage = shutil.disk_usage(str(cfg.archive_dir))
            except Exception:
                try:
                    usage = shutil.disk_usage(str(cfg.live_dir))
                except Exception as e:
                    logger.warning("disk_usage failed: %s", e)
                    return 0
            pct = int(usage.used * 100 / usage.total) if usage.total else 0
            if pct < Archiver.DISK_FULL_PCT:
                return 0
            all_files = []
            for d in (cfg.archive_dir, cfg.live_dir):
                try:
                    for p in d.glob("*.parquet"):
                        all_files.append(p)
                except Exception:
                    continue
            all_files.sort(key=lambda x: x.stat().st_mtime)
            removed = 0
            for p in all_files:
                try:
                    p.unlink()
                    removed += 1
                    usage = shutil.disk_usage(str(p.parent))
                    pct = int(usage.used * 100 / usage.total) if usage.total else 0
                    if pct < Archiver.DISK_FULL_PCT:
                        break
                except Exception as e:
                    logger.warning("enforce delete failed %s: %s", p, e)
            if removed > 0:
                logger.warning("DISK_FULL_PCT trim removed=%d", removed)
            return removed

        async with self._rotation_lock:
            return await asyncio.to_thread(_enforce_sync, self._config)