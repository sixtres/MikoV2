# YAMA Y-264 REVISE + Y-310: store_flush_suspended counter+Lock refcount==0 clear ALWAYS
# YAMA Y-265: sealed_lock ayri (fill_lock'tan)
# YAMA Y-269: sqlite_timeout_ms (whitelist)
# YAMA Y-285: optimistic retry loop max 3
# YAMA Y-353: Stateless - no global mutable, DI via __init__
# YAMA Y-358: asyncio.Lock (fill_lock DI)

"""
SqliteWriter - WAL mode for STATE (positions, orders).

Y-264 REVISE + Y-310: store_flush_suspended counter+Lock refcount==0 clear ALWAYS
Y-265: sealed_lock separate from fill_lock (DI)
Y-269: sqlite_timeout_ms int whitelist
Y-285: optimistic retry loop max 3 for versioned update
Y-353: DI, no global
Y-358: fill_lock asyncio.Lock via DI
"""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True, slots=True)
class SqliteWriterConfig:
    db_path: Path
    sqlite_timeout_ms: int = 5000 # Y-269 whitelist
    max_retries: int = 3 # Y-285

class SqliteWriter:
    """
    SQLite WAL writer for STATE (positions, orders).

    Y-264 REVISE: store_flush_suspended counter+Lock refcount==0 clear ALWAYS
    Y-265: sealed_lock separate (fill_lock)
    Y-269: sqlite_timeout_ms int
    Y-285: optimistic retry max 3
    Y-310: refcount handling for flush suspension
    Y-353: DI, no global state
    Y-358: fill_lock asyncio.Lock via DI
    """

    def __init__(
        self,
        config: SqliteWriterConfig,
        fill_lock: asyncio.Lock, # Y-339 hierarchy
    ) -> None:
        self._config = config
        self._conn: sqlite3.Connection | None = None
        self._fill_lock = fill_lock

    async def connect(self) -> None:
        """
        Connect and enable WAL mode.

        PRAGMA journal_mode=WAL
        PRAGMA busy_timeout=sqlite_timeout_ms
        DDL:
          positions (id, avg, original_planned_entry IMMUTABLE, current_tp_shifted, current_sl_shifted, version, ...)
          orders
          sealed_at_ms
          emergency_pending
          original_tp, original_sl IMMUTABLE
        """
        raise NotImplementedError("FAZ 4")

    async def execute_wal(self, payload: dict[str, Any]) -> None:
        """
        Direct WAL write, bypass state_queue (Y-341 related).

        Used by emergency_persist_state with 2s timeout externally.
        """
        raise NotImplementedError("FAZ 4")

    async def fetch(self, query: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        """SELECT query under fill_lock."""
        raise NotImplementedError("FAZ 4")

    async def get_version(self, position_id: str) -> int:
        """Read optimistic version (Y-285)."""
        raise NotImplementedError("FAZ 4")

    async def update_position_versioned(
        self,
        position_id: str,
        new_avg: float,
        new_tp: float,
        new_sl: float,
        expected_version: int,
    ) -> bool:
        """
        Versioned UPDATE (Y-285).

        WHERE version = expected_version.
        Returns False on VersionConflict, caller retries max 3.
        """
        raise NotImplementedError("FAZ 4")

    async def close(self) -> None:
        """Close connection."""
        raise NotImplementedError("FAZ 4")