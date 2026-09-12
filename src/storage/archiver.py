# YAMA Y-331: gunluk arsivleme UTC 00:00 ayri task, supervisor TaskGroup
# YAMA ARCHIVE-ATOMIC: asyncio.to_thread atomic.tmp->rename two-phase rotation
# YAMA ORPHAN: _closed 5m,.deleted 1h, lock file PID+timestamp PID check
# YAMA DISK-FULL: 90% oldest delete
# YAMA Y-353: DI, no global
# YAMA Y-358: asyncio.Lock for rotation serialization

"""
Archiver - daily archive task for Parquet store.

Y-331: daily archive at UTC 00:00 as separate task, supervisor TaskGroup
ARCHIVE-ATOMIC: asyncio.to_thread + atomic.tmp->rename two-phase rotation
ORPHAN: _closed 5m,.deleted 1h, lock file PID+timestamp PID check
DISK-FULL: 90% oldest delete
Y-353: DI
Y-358: rotation_lock asyncio.Lock via DI
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

@dataclass(frozen=True, slots=True)
class ArchiverConfig:
    live_dir: Path
    archive_dir: Path
    snappy_level: int = 9
    live_days: int = 7
    archive_days: int = 365

class Archiver:
    """
    Daily archiver for Parquet files.

    Y-331: daily archive at UTC 00:00 as separate task
    ARCHIVE-ATOMIC: asyncio.to_thread + atomic.tmp->rename two-phase rotation
    ORPHAN: _closed 5m,.deleted 1h, lock PID+timestamp PID check
    DISK-FULL: 90% oldest delete
    Y-353: DI, no global
    Y-358: asyncio.Lock for rotation serialization
    """

    ARCHIVE_UTC_HOUR: Final[int] = 0
    ORPHAN_CLOSED_MS: Final[int] = 300000
    ORPHAN_DELETED_MS: Final[int] = 3600000
    DISK_FULL_PCT: Final[int] = 90

    def __init__(
        self,
        config: ArchiverConfig,
        rotation_lock: asyncio.Lock, # Y-358 DI
    ) -> None:
        self._config = config
        self._rotation_lock = rotation_lock

    async def run_daily(self) -> None:
        """
        Run archive daily at UTC 00:00 (Y-331).

        Uses asyncio.to_thread for Parquet compression.
        Lock file PID+timestamp with PID check (ORPHAN constant).
        """
        raise NotImplementedError("FAZ 4")

    async def archive_file(self, file_path: Path) -> Path:
        """
        Archive single file with snappy 9.

        Atomic.tmp -> rename (ARCHIVE-ATOMIC).
        """
        raise NotImplementedError("FAZ 4")

    async def trim_old(self) -> int:
        """
        Trim archives older than archive_days.

        Returns deleted count.
        """
        raise NotImplementedError("FAZ 4")

    async def recover_orphans(self) -> int:
        """
        Recover _closed orphans >5m,.deleted >1h (ORPHAN).

        Returns recovered/deleted count.
        """
        raise NotImplementedError("FAZ 4")

    async def enforce_disk_limit(self) -> int:
        """
        Disk full 90% oldest delete (DISK-FULL).

        Returns deleted count.
        """
        raise NotImplementedError("FAZ 4")