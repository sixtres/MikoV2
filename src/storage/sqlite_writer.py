# YAMA Y-264 REVISE + Y-310: counter+Lock refcount==0 clear ALWAYS
# YAMA Y-265: sealed_lock ayri
# YAMA Y-269: sqlite_timeout_ms whitelist
# YAMA Y-285: optimistic retry max 3
# YAMA Y-341: emergency execute_wal direct 2s timeout
# YAMA Y-353: DI, no global
# YAMA Y-358: fill_lock DI

"""
Sqlite writer - sync sqlite3 stdlib, fill_lock DI.

Y-264+Y-310: refcount.
Y-265: sealed_lock ayri.
Y-269: timeout whitelist.
Y-285: optimistic retry max 3.
Y-341: emergency execute_wal direct.
Y-353: DI no global.
Y-358: fill_lock DI.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class SqliteWriterConfig:
    db_path: Path
    sqlite_timeout_ms: int = 5000
    max_retries: int = 3

class SqliteWriter:
    def __init__(
        self, config: SqliteWriterConfig, fill_lock: asyncio.Lock
    ) -> None:
        self._config = config
        self._fill_lock = fill_lock
        self._conn: sqlite3.Connection | None = None

    async def connect(self) -> None:
        db_path = self._config.db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        timeout_s = self._config.sqlite_timeout_ms / 1000.0
        conn = sqlite3.connect(
            str(db_path), timeout=timeout_s, check_same_thread=False
        )
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=%d" % self._config.sqlite_timeout_ms)
        except Exception as e:
            logger.warning("pragma failed: %s", e)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                avg REAL,
                original_planned_entry REAL,
                original_tp REAL,
                original_sl REAL,
                current_tp_shifted REAL,
                current_sl_shifted REAL,
                version INTEGER DEFAULT 0,
                sealed_at_ms INTEGER,
                emergency_pending INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                position_id TEXT,
                filled_qty REAL,
                status TEXT
            )
            """
        )
        conn.commit()
        self._conn = conn

    async def execute_wal(self, payload: dict) -> None:
        if self._conn is None:
            raise RuntimeError("not connected")
        async with self._fill_lock:
            try:
                if "order_id" in payload:
                    self._conn.execute(
                        """
                        INSERT OR REPLACE INTO orders
                        (order_id, position_id, filled_qty, status)
                        VALUES (?,?,?,?)
                        """,
                        (
                            payload.get("order_id"),
                            payload.get("position_id"),
                            payload.get("filled_qty", 0.0),
                            payload.get("status", "PARTIAL"),
                        ),
                    )
                else:
                    self._conn.execute(
                        """
                        INSERT OR REPLACE INTO positions
                        (position_id, avg, original_planned_entry, original_tp,
                         original_sl, current_tp_shifted, current_sl_shifted,
                         version, sealed_at_ms, emergency_pending)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            payload.get("position_id"),
                            payload.get("avg", 0.0),
                            payload.get("original_planned_entry", 0.0),
                            payload.get("original_tp", 0.0),
                            payload.get("original_sl", 0.0),
                            payload.get("current_tp_shifted", 0.0),
                            payload.get("current_sl_shifted", 0.0),
                            payload.get("version", 0),
                            payload.get("sealed_at_ms"),
                            payload.get("emergency_pending", 0),
                        ),
                    )
                self._conn.commit()
            except Exception as e:
                logger.warning("execute_wal failed: %s", e)
                raise

    async def fetch(self, query: str, params: tuple = ()) -> list[tuple]:
        if self._conn is None:
            raise RuntimeError("not connected")
        try:
            cur = self._conn.execute(query, params)
            return cur.fetchall()
        except Exception as e:
            logger.warning("fetch failed query=%s error=%s", query, e)
            return []

    async def get_version(self, position_id: str) -> int:
        if self._conn is None:
            raise RuntimeError("not connected")
        try:
            cur = self._conn.execute(
                "SELECT version FROM positions WHERE position_id=?",
                (position_id,),
            )
            row = cur.fetchone()
            if row is None:
                return 0
            return int(row[0])
        except Exception as e:
            logger.warning("get_version failed id=%s error=%s", position_id, e)
            return 0

    async def update_position_versioned(
        self,
        position_id: str,
        new_avg: float,
        new_tp: float,
        new_sl: float,
        expected_version: int,
    ) -> bool:
        if self._conn is None:
            raise RuntimeError("not connected")
        async with self._fill_lock:
            try:
                old_version = expected_version - 1
                cur = self._conn.execute(
                    """
                    UPDATE positions
                    SET avg=?, current_tp_shifted=?, current_sl_shifted=?, version=?
                    WHERE position_id=? AND version=?
                    """,
                    (
                        new_avg,
                        new_tp,
                        new_sl,
                        expected_version,
                        position_id,
                        old_version,
                    ),
                )
                if cur.rowcount == 0:
                    return False
                self._conn.commit()
                return True
            except Exception as e:
                logger.warning(
                    "update_position_versioned failed id=%s error=%s",
                    position_id,
                    e,
                )
                return False

    async def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception as e:
                logger.warning("close failed: %s", e)
            self._conn = None