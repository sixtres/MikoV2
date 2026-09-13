# YAMA Y-264 REVISE + Y-310: counter+Lock refcount==0 clear ALWAYS
# YAMA Y-265: sealed_lock ayri
# YAMA Y-269: sqlite_timeout_ms whitelist
# YAMA Y-285: optimistic retry max 3
# YAMA Y-341: emergency execute_wal direct 2s timeout
# YAMA Y-353: DI, no global
# YAMA Y-358: fill_lock DI
# REV7: dashboard + backtest icin sema genisletme

"""
Sqlite writer - sync sqlite3 stdlib, fill_lock DI.

Tables:
  positions          - full lifecycle (open/partial/closed)
  orders             - order fill details
  whale_events       - whale detections for dashboard
  equity_snapshots   - time series for equity chart
  daily_stats        - daily/weekly aggregates
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
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

    # ------------------------------------------------------------------ connect

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

        # ---- positions (full lifecycle)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                symbol TEXT,
                side TEXT,
                status TEXT DEFAULT 'open',
                opened_at_ms INTEGER,
                closed_at_ms INTEGER,
                close_reason TEXT,
                avg REAL,
                qty_open REAL,
                qty_remaining REAL,
                original_planned_entry REAL,
                original_tp REAL,
                original_sl REAL,
                current_tp_shifted REAL,
                current_sl_shifted REAL,
                be_active INTEGER DEFAULT 0,
                trailing_active INTEGER DEFAULT 0,
                second_entry_count INTEGER DEFAULT 0,
                whale_trust_score INTEGER DEFAULT 0,
                universe_status TEXT,
                realized_pnl REAL DEFAULT 0,
                fee_total REAL DEFAULT 0,
                r_multiple REAL,
                version INTEGER DEFAULT 0,
                sealed_at_ms INTEGER,
                emergency_pending INTEGER DEFAULT 0
            )
            """
        )

        # ---- orders
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                position_id TEXT,
                symbol TEXT,
                side TEXT,
                filled_qty REAL,
                fill_price REAL,
                fee REAL,
                slippage REAL,
                status TEXT,
                filled_at_ms INTEGER,
                created_at_ms INTEGER
            )
            """
        )

        # ---- whale_events
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS whale_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                band_key TEXT,
                price REAL,
                oi_delta_usd REAL,
                fill_ratio REAL,
                order_lifetime_ms INTEGER,
                is_real INTEGER,
                is_spoof INTEGER,
                trust_score INTEGER,
                exchange_ts_ms INTEGER,
                created_at_ms INTEGER
            )
            """
        )

        # ---- equity_snapshots
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS equity_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_ms INTEGER,
                balance REAL,
                equity REAL,
                unrealized_pnl REAL,
                realized_today REAL,
                drawdown_pct REAL,
                open_positions INTEGER
            )
            """
        )

        # ---- daily_stats
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_stats (
                date_utc TEXT PRIMARY KEY,
                start_equity REAL,
                end_equity REAL,
                realized_pnl REAL,
                fees REAL,
                trades_count INTEGER,
                win_count INTEGER,
                loss_count INTEGER
            )
            """
        )

        # ---- indexes
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_opened ON positions(opened_at_ms)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_position ON orders(position_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_whale_symbol_ts "
            "ON whale_events(symbol, exchange_ts_ms)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_whale_created "
            "ON whale_events(created_at_ms)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_equity_ts "
            "ON equity_snapshots(ts_ms)"
        )

        conn.commit()
        self._conn = conn

    # ------------------------------------------------------------------ legacy (kept for compat)

    async def execute_wal(self, payload: dict) -> None:
        """Generic WAL write. Prefer specific methods below."""
        if self._conn is None:
            raise RuntimeError("not connected")
        async with self._fill_lock:
            try:
                if "order_id" in payload:
                    self._conn.execute(
                        """
                        INSERT OR REPLACE INTO orders
                        (order_id, position_id, symbol, side, filled_qty,
                         fill_price, fee, slippage, status,
                         filled_at_ms, created_at_ms)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            payload.get("order_id"),
                            payload.get("position_id"),
                            payload.get("symbol"),
                            payload.get("side"),
                            payload.get("filled_qty", 0.0),
                            payload.get("fill_price", 0.0),
                            payload.get("fee", 0.0),
                            payload.get("slippage", 0.0),
                            payload.get("status", "PARTIAL"),
                            payload.get("filled_at_ms"),
                            payload.get("created_at_ms", int(time.time() * 1000)),
                        ),
                    )
                else:
                    self._conn.execute(
                        """
                        INSERT OR REPLACE INTO positions
                        (position_id, symbol, side, status, opened_at_ms,
                         closed_at_ms, close_reason, avg, qty_open,
                         qty_remaining, original_planned_entry, original_tp,
                         original_sl, current_tp_shifted, current_sl_shifted,
                         be_active, trailing_active, second_entry_count,
                         whale_trust_score, universe_status, realized_pnl,
                         fee_total, r_multiple, version, sealed_at_ms,
                         emergency_pending)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            payload.get("position_id"),
                            payload.get("symbol"),
                            payload.get("side"),
                            payload.get("status", "open"),
                            payload.get("opened_at_ms"),
                            payload.get("closed_at_ms"),
                            payload.get("close_reason"),
                            payload.get("avg", 0.0),
                            payload.get("qty_open", 0.0),
                            payload.get("qty_remaining", 0.0),
                            payload.get("original_planned_entry", 0.0),
                            payload.get("original_tp", 0.0),
                            payload.get("original_sl", 0.0),
                            payload.get("current_tp_shifted", 0.0),
                            payload.get("current_sl_shifted", 0.0),
                            1 if payload.get("be_active") else 0,
                            1 if payload.get("trailing_active") else 0,
                            payload.get("second_entry_count", 0),
                            payload.get("whale_trust_score", 0),
                            payload.get("universe_status"),
                            payload.get("realized_pnl", 0.0),
                            payload.get("fee_total", 0.0),
                            payload.get("r_multiple"),
                            payload.get("version", 0),
                            payload.get("sealed_at_ms"),
                            1 if payload.get("emergency_pending") else 0,
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

    # ------------------------------------------------------------------ position lifecycle

    async def open_position(self, payload: dict) -> None:
        """Insert new position with status='open'. Idempotent if PK exists."""
        if self._conn is None:
            raise RuntimeError("not connected")
        async with self._fill_lock:
            try:
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO positions (
                        position_id, symbol, side, status, opened_at_ms,
                        avg, qty_open, qty_remaining,
                        original_planned_entry, original_tp, original_sl,
                        current_tp_shifted, current_sl_shifted,
                        whale_trust_score, universe_status, version
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        payload["position_id"],
                        payload.get("symbol"),
                        payload.get("side"),
                        "open",
                        payload.get("opened_at_ms", int(time.time() * 1000)),
                        payload.get("avg", 0.0),
                        payload.get("qty_open", 0.0),
                        payload.get("qty_remaining", payload.get("qty_open", 0.0)),
                        payload.get("original_planned_entry", payload.get("avg", 0.0)),
                        payload.get("original_tp", 0.0),
                        payload.get("original_sl", 0.0),
                        payload.get("current_tp_shifted", 0.0),
                        payload.get("current_sl_shifted", 0.0),
                        payload.get("whale_trust_score", 0),
                        payload.get("universe_status"),
                        payload.get("version", 0),
                    ),
                )
                self._conn.commit()
            except Exception as e:
                logger.warning("open_position failed: %s", e)
                raise

    async def close_position(
        self,
        position_id: str,
        close_reason: str,
        realized_pnl: float,
        fee_total: float,
        r_multiple: float | None,
    ) -> None:
        """Mark position closed with outcome."""
        if self._conn is None:
            raise RuntimeError("not connected")
        async with self._fill_lock:
            try:
                self._conn.execute(
                    """
                    UPDATE positions SET
                        status='closed',
                        closed_at_ms=?,
                        close_reason=?,
                        realized_pnl=?,
                        fee_total=?,
                        r_multiple=?
                    WHERE position_id=?
                    """,
                    (
                        int(time.time() * 1000),
                        close_reason,
                        realized_pnl,
                        fee_total,
                        r_multiple,
                        position_id,
                    ),
                )
                self._conn.commit()
            except Exception as e:
                logger.warning("close_position failed: %s", e)
                raise

    async def list_open_positions(self) -> list[tuple]:
        return await self.fetch(
            "SELECT position_id, symbol, side, opened_at_ms, avg, qty_open, "
            "qty_remaining, current_tp_shifted, current_sl_shifted, "
            "be_active, trailing_active, whale_trust_score, universe_status, "
            "version, emergency_pending "
            "FROM positions WHERE status IN ('open','partial') "
            "ORDER BY opened_at_ms DESC"
        )

    async def list_closed_positions(self, limit: int = 100) -> list[tuple]:
        return await self.fetch(
            "SELECT position_id, symbol, side, opened_at_ms, closed_at_ms, "
            "close_reason, avg, realized_pnl, fee_total, r_multiple "
            "FROM positions WHERE status='closed' "
            "ORDER BY closed_at_ms DESC LIMIT ?",
            (limit,),
        )

    # ------------------------------------------------------------------ whale events

    async def insert_whale_event(self, payload: dict) -> None:
        if self._conn is None:
            raise RuntimeError("not connected")
        async with self._fill_lock:
            try:
                self._conn.execute(
                    """
                    INSERT INTO whale_events (
                        symbol, band_key, price, oi_delta_usd, fill_ratio,
                        order_lifetime_ms, is_real, is_spoof, trust_score,
                        exchange_ts_ms, created_at_ms
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        payload.get("symbol"),
                        payload.get("band_key"),
                        payload.get("price", 0.0),
                        payload.get("oi_delta_usd", 0.0),
                        payload.get("fill_ratio", 0.0),
                        payload.get("order_lifetime_ms", 0),
                        1 if payload.get("is_real") else 0,
                        1 if payload.get("is_spoof") else 0,
                        payload.get("trust_score", 0),
                        payload.get("exchange_ts_ms", 0),
                        payload.get("created_at_ms", int(time.time() * 1000)),
                    ),
                )
                self._conn.commit()
            except Exception as e:
                logger.warning("insert_whale_event failed: %s", e)
                raise

    async def list_recent_whales(self, limit: int = 50) -> list[tuple]:
        return await self.fetch(
            "SELECT id, symbol, band_key, price, oi_delta_usd, fill_ratio, "
            "order_lifetime_ms, is_real, is_spoof, trust_score, "
            "exchange_ts_ms, created_at_ms "
            "FROM whale_events ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    # ------------------------------------------------------------------ equity snapshots

    async def insert_equity_snapshot(self, payload: dict) -> None:
        if self._conn is None:
            raise RuntimeError("not connected")
        async with self._fill_lock:
            try:
                self._conn.execute(
                    """
                    INSERT INTO equity_snapshots (
                        ts_ms, balance, equity, unrealized_pnl,
                        realized_today, drawdown_pct, open_positions
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        payload.get("ts_ms", int(time.time() * 1000)),
                        payload.get("balance", 0.0),
                        payload.get("equity", 0.0),
                        payload.get("unrealized_pnl", 0.0),
                        payload.get("realized_today", 0.0),
                        payload.get("drawdown_pct", 0.0),
                        payload.get("open_positions", 0),
                    ),
                )
                self._conn.commit()
            except Exception as e:
                logger.warning("insert_equity_snapshot failed: %s", e)
                raise

    async def list_equity_snapshots(
        self, since_ms: int, limit: int = 2000
    ) -> list[tuple]:
        return await self.fetch(
            "SELECT ts_ms, balance, equity, unrealized_pnl, realized_today, "
            "drawdown_pct, open_positions "
            "FROM equity_snapshots WHERE ts_ms >= ? "
            "ORDER BY ts_ms ASC LIMIT ?",
            (since_ms, limit),
        )

    # ------------------------------------------------------------------ daily stats

    async def upsert_daily_stats(self, payload: dict) -> None:
        if self._conn is None:
            raise RuntimeError("not connected")
        async with self._fill_lock:
            try:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_stats (
                        date_utc, start_equity, end_equity, realized_pnl,
                        fees, trades_count, win_count, loss_count
                    ) VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        payload["date_utc"],
                        payload.get("start_equity", 0.0),
                        payload.get("end_equity", 0.0),
                        payload.get("realized_pnl", 0.0),
                        payload.get("fees", 0.0),
                        payload.get("trades_count", 0),
                        payload.get("win_count", 0),
                        payload.get("loss_count", 0),
                    ),
                )
                self._conn.commit()
            except Exception as e:
                logger.warning("upsert_daily_stats failed: %s", e)
                raise

    async def get_daily_stats(self, date_utc: str) -> tuple | None:
        rows = await self.fetch(
            "SELECT date_utc, start_equity, end_equity, realized_pnl, fees, "
            "trades_count, win_count, loss_count "
            "FROM daily_stats WHERE date_utc=?",
            (date_utc,),
        )
        return rows[0] if rows else None

    # ------------------------------------------------------------------ version / optimistic

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
                    SET avg=?, current_tp_shifted=?, current_sl_shifted=?,
                        version=?
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

    # ------------------------------------------------------------------ close

    async def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception as e:
                logger.warning("close failed: %s", e)
            self._conn = None