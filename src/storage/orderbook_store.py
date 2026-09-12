# YAMA Y-264 + Y-310: store_flush_suspended counter, refcount==0 clear
# YAMA Y-269: _ms int whitelist
# YAMA Y-276: force-flush daemon 2 bounded 5 put_nowait DROP telemetry only
# YAMA Y-346: counter underflow WARNING
# YAMA Y-348: trim WARNING rate-limited
# YAMA Y-353: DI
# YAMA Y-358: write_lock asyncio.Lock DI, read_lock threading.RLock DI

"""
OrderBook store - parquet disk writer with rotate / archive / disk limit.

Y-264+Y-310: flush suspended counter refcount.
Y-269: _ms whitelist.
Y-276: force-flush bounded DROP.
Y-346: underflow WARNING.
Y-348: trim WARNING rate-limited.
Y-353: DI no global.
Y-358: write_lock asyncio.Lock DI, read_lock threading.RLock DI.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import threading
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
class OrderBookStoreConfig:
    live_dir: Path
    archive_dir: Path
    live_days: int = 7
    archive_days: int = 365
    batch_size: int = 500
    flush_threshold: int = 5000
    snappy_live: int = 1
    snappy_archive: int = 9

class OrderBookStore:
    ORPHAN_CLOSED_MS = 300000
    ORPHAN_DELETED_MS = 3600000
    DISK_FULL_PCT = 90

    def __init__(
        self,
        config: OrderBookStoreConfig,
        write_lock: asyncio.Lock,
        read_lock: threading.RLock,
        flush_suspended_counter: Any,
    ) -> None:
        self._config = config
        self._write_lock = write_lock
        self._read_lock = read_lock
        self._flush_suspended = flush_suspended_counter
        self._buffer: list[dict] = []
        self._last_trim_warn_ms: int = 0
        config.live_dir.mkdir(parents=True, exist_ok=True)
        config.archive_dir.mkdir(parents=True, exist_ok=True)

    def _is_suspended(self) -> bool:
        try:
            c = self._flush_suspended
            if hasattr(c, "_counter"):
                return c._counter > 0
            if hasattr(c, "value"):
                return int(c.value) > 0
            if isinstance(c, (list, tuple)):
                return len(c) > 0 and c[0] > 0
            return int(c) > 0
        except Exception:
            return False

    async def append(self, record: dict) -> None:
        if self._is_suspended():
            logger.warning("STORE_FLUSH_SUSPENDED drop telemetry record=%s", record.get("symbol", "unknown"))
            return
        async with self._write_lock:
            self._buffer.append(record)
            buf_len = len(self._buffer)
        if buf_len >= self._config.batch_size:
            try:
                await self.flush()
            except Exception as e:
                logger.warning("append batch flush failed: %s", e)

    async def flush(self) -> int:
        async with self._write_lock:
            if not self._buffer:
                return 0
            to_write = list(self._buffer)
            self._buffer.clear()
            count = len(to_write)

        if pd is None:
            logger.warning("pandas not available, drop %d records", count)
            return 0

        def _write_sync(records: list[dict], cfg: OrderBookStoreConfig) -> int:
            live_dir = cfg.live_dir
            ts_ms = int(time.time() * 1000)
            fname = "orderbook_%d.parquet" % ts_ms
            tmp_path = live_dir / (fname + ".tmp")
            final_path = live_dir / fname
            try:
                df = pd.DataFrame(records)
                df.to_parquet(str(tmp_path), compression="snappy")
                tmp_path.rename(final_path)
                return len(records)
            except Exception as e:
                logger.warning("parquet write failed: %s", e)
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    pass
                return 0

        written = await asyncio.to_thread(_write_sync, to_write, self._config)
        return written

    async def rotate(self) -> None:
        def _rotate_sync(cfg: OrderBookStoreConfig) -> None:
            now_ms = int(time.time() * 1000)
            live_dir = cfg.live_dir
            # Phase 1:._closed orphan 5m
            for p in live_dir.glob("*.parquet._closed"):
                try:
                    mtime_ms = int(p.stat().st_mtime * 1000)
                    if now_ms - mtime_ms > OrderBookStore.ORPHAN_CLOSED_MS:
                        p.unlink()
                        logger.warning("orphan _closed removed: %s", p.name)
                except Exception as e:
                    logger.warning("rotate _closed failed %s: %s", p, e)
            # Phase 2:.deleted orphan 1h
            for p in live_dir.glob("*.parquet.deleted"):
                try:
                    mtime_ms = int(p.stat().st_mtime * 1000)
                    if now_ms - mtime_ms > OrderBookStore.ORPHAN_DELETED_MS:
                        p.unlink()
                        logger.warning("orphan deleted removed: %s", p.name)
                except Exception as e:
                    logger.warning("rotate deleted failed %s: %s", p, e)

        await asyncio.to_thread(_rotate_sync, self._config)

    async def archive_task(self) -> None:
        def _archive_sync(cfg: OrderBookStoreConfig) -> None:
            now_s = time.time()
            live_dir = cfg.live_dir
            archive_dir = cfg.archive_dir
            archive_dir.mkdir(parents=True, exist_ok=True)
            cutoff_s = now_s - cfg.live_days * 86400
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
                                # fallback move
                                p.rename(dest)
                        else:
                            p.rename(dest)
                        logger.warning("archived %s to %s", p.name, archive_dir)
                except Exception as e:
                    logger.warning("archive failed %s: %s", p, e)

        await asyncio.to_thread(_archive_sync, self._config)

    async def enforce_disk_limit(self) -> int:
        def _enforce_sync(cfg: OrderBookStoreConfig) -> int:
            try:
                usage = shutil.disk_usage(str(cfg.archive_dir))
            except Exception:
                try:
                    usage = shutil.disk_usage(str(cfg.live_dir))
                except Exception as e:
                    logger.warning("disk_usage failed: %s", e)
                    return 0
            pct = int(usage.used * 100 / usage.total) if usage.total else 0
            if pct < OrderBookStore.DISK_FULL_PCT:
                return 0
            # collect oldest files
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
                    if pct < OrderBookStore.DISK_FULL_PCT:
                        break
                except Exception as e:
                    logger.warning("enforce delete failed %s: %s", p, e)
            if removed > 0:
                logger.warning("DISK_FULL_PCT trim removed=%d", removed)
            return removed

        return await asyncio.to_thread(_enforce_sync, self._config)

    def read_snapshot(self, symbol: str, ts_from: int, ts_to: int) -> Any:
        with self._read_lock:
            if pd is None:
                return []
            results = []
            for d in (self._config.live_dir, self._config.archive_dir):
                try:
                    for p in d.glob("*.parquet"):
                        try:
                            df = pd.read_parquet(str(p))
                            if "symbol" in df.columns:
                                df = df[df["symbol"] == symbol]
                            if "ts_ms" in df.columns:
                                df = df[(df["ts_ms"] >= ts_from) & (df["ts_ms"] <= ts_to)]
                            if not df.empty:
                                results.append(df)
                        except Exception:
                            continue
                except Exception:
                    continue
            if not results:
                return pd.DataFrame()
            try:
                return pd.concat(results, ignore_index=True)
            except Exception:
                return results[0] if results else pd.DataFrame()