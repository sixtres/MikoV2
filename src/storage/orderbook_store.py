# YAMA Y-264 REVISE + Y-310: store_flush_suspended counter+Lock, refcount==0 clear ALWAYS
# YAMA Y-269: _ms int whitelist
# YAMA Y-276: force-flush daemon 2 bounded 5 put_nowait DROP telemetry only, zero-disk
# YAMA Y-346: counter underflow WARNING
# YAMA Y-348: trim WARNING rate-limited
# YAMA Y-353: Stateless - no global mutable, DI
# YAMA Y-358: asyncio.Lock (write lock)

"""
OrderBookStore - Parquet disk writer with snappy and rotation.

Y-264 REVISE + Y-310: store_flush_suspended counter+Lock refcount==0 clear ALWAYS
Y-269: _ms fields int whitelist (flush_threshold is records, not ms)
Y-276: force-flush daemon 2 bounded 5 put_nowait DROP telemetry only
Y-346: counter underflow WARNING
Y-348: trim WARNING rate-limited
Y-353: DI, no global state
Y-358: asyncio.Lock via DI

REV5:
  snappy live1 archive9
  live 7 archive 365
  atomic.tmp->rename two-phase rotation
  _closed orphan 5m.deleted 1h
  lock PID+timestamp PID check
  batch 500 flush 5000 records
  disk full 90% oldest delete
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

@dataclass(frozen=True, slots=True)
class OrderBookStoreConfig:
    live_dir: Path
    archive_dir: Path
    live_days: int = 7 # REV5
    archive_days: int = 365 # REV5
    batch_size: int = 500 # REV5
    flush_threshold: int = 5000 # REV5 records count
    snappy_live: int = 1 # REV5
    snappy_archive: int = 9 # REV5

class OrderBookStore:
    """
    Parquet-based L2 orderbook disk store.

    Y-264 REVISE + Y-310: store_flush_suspended counter+Lock
    Y-276: force-flush daemon 2 bounded 5 put_nowait DROP telemetry only
    Y-346: counter underflow WARNING
    Y-348: trim WARNING rate-limited
    Y-353: DI
    Y-358: asyncio.Lock

    REV5:
      snappy live1 archive9 live 7d archive 365d
      atomic.tmp->rename two-phase rotation
      _closed orphan 5m,.deleted 1h
      lock PID+timestamp PID check
      00:00.lock
      batch 500 flush 5000 records
      zero-disk store_flush_suspended counter+Lock refcount==0 clear ALWAYS
      disk full 90% oldest delete
      next_candle extrapolate max(0)
    """

    ORPHAN_CLOSED_MS: Final[int] = 300000 # 5m REV5
    ORPHAN_DELETED_MS: Final[int] = 3600000 # 1h REV5
    DISK_FULL_PCT: Final[int] = 90

    def __init__(
        self,
        config: OrderBookStoreConfig,
        write_lock: asyncio.Lock, # Y-358 DI
        read_lock: threading.RLock, # single RLock copy-on-read
        flush_suspended_counter: Any, # Y-264/310 DI
    ) -> None:
        self._config = config
        self._write_lock = write_lock
        self._read_lock = read_lock
        self._flush_counter = flush_suspended_counter
        self._buffer: list[Any] = []
        self._flush_count: int = 0

    async def append(self, record: dict[str, Any]) -> None:
        """
        Append L2 record to buffer.

        Y-264: if store_flush_suspended, drop telemetry only, keep state
        Y-310: refcount==0 -> clear ALWAYS, never leak
        Y-346: underflow WARNING
        Flush when buffer >= batch_size (500).
        """
        raise NotImplementedError("FAZ 4")

    async def flush(self) -> int:
        """
        Flush buffer to Parquet with snappy live1.

        Atomic.tmp -> rename.
        Returns written count.
        """
        raise NotImplementedError("FAZ 4")

    async def rotate(self) -> None:
        """
        Two-phase rotation: rename current to._closed, then archive.

        Orphan recovery: _closed > 5m -> archive,.deleted > 1h -> delete.
        Uses ORPHAN_CLOSED_MS / ORPHAN_DELETED_MS constants.
        Y-348: trim WARNING rate-limited
        """
        raise NotImplementedError("FAZ 4")

    async def archive_task(self) -> None:
        """
        Archiver asyncio.to_thread, snappy archive9.

        Runs daily at UTC 00:00.
        Lock file PID+timestamp with PID check.
        """
        raise NotImplementedError("FAZ 4")

    async def enforce_disk_limit(self) -> None:
        """
        Disk full 90%: delete oldest archive files.

        Uses DISK_FULL_PCT constant.
        Y-348: WARNING rate-limited.
        """
        raise NotImplementedError("FAZ 4")

    def read_snapshot(self, symbol: str, ts_from: int, ts_to: int) -> Any:
        """
        Copy-on-read under single RLock (no await).

        Single RLock for all reads.
        """
        raise NotImplementedError("FAZ 4")