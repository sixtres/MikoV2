# REV7: equity snapshot writer - 60s timer + close event
# YAMA Y-353: DI, no global
# YAMA Y-358: asyncio.Lock DI

"""
Equity tracker - writes equity_snapshots to DB.

Triggers:
  - 60s timer while positions are open
  - immediately after a position close

Sources:
  - positions table (open positions)
  - mark_price_cache (current marks)
  - daily_stats (realized today)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .mark_price_cache import MarkPriceCache
    from .sqlite_writer import SqliteWriter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EquityTrackerConfig:
    timer_interval_s: float = 60.0
    base_balance: float = 1000.0


class EquityTracker:
    def __init__(
        self,
        config: EquityTrackerConfig,
        sqlite: "SqliteWriter",
        mark_cache: "MarkPriceCache",
        fill_lock: asyncio.Lock,
    ) -> None:
        self._config = config
        self._sqlite = sqlite
        self._mark_cache = mark_cache
        self._fill_lock = fill_lock
        self._realized_today: float = 0.0
        self._peak_equity: float = config.base_balance
        self._last_snapshot_ms: int = 0

    async def compute_snapshot(self) -> dict | None:
        """
        Compute current equity. Returns dict or None on failure.
        """
        try:
            async with self._fill_lock:
                rows = await self._sqlite.list_open_positions()
        except Exception as e:
            logger.warning("list_open_positions failed: %s", e)
            return None

        unrealized = 0.0
        open_count = 0
        for row in rows or []:
            open_count += 1
            # row layout: position_id, symbol, side, opened_at_ms, avg,
            #             qty_open, qty_remaining, ...
            symbol = row[1]
            side = row[2]
            avg = float(row[4] or 0.0)
            qty_remaining = float(row[6] or 0.0)
            entry = await self._mark_cache.get(symbol)
            if entry is None:
                continue
            if side == "LONG":
                unrealized += (entry - avg) * qty_remaining
            else:
                unrealized += (avg - entry) * qty_remaining

        equity = self._config.base_balance + self._realized_today + unrealized
        self._peak_equity = max(self._peak_equity, equity)
        drawdown_pct = 0.0
        if self._peak_equity > 0:
            drawdown_pct = (self._peak_equity - equity) / self._peak_equity

        return {
            "ts_ms": int(time.time() * 1000),
            "balance": self._config.base_balance + self._realized_today,
            "equity": equity,
            "unrealized_pnl": unrealized,
            "realized_today": self._realized_today,
            "drawdown_pct": drawdown_pct,
            "open_positions": open_count,
        }

    async def snapshot_once(self) -> bool:
        """Compute + write one snapshot. Returns True if written."""
        snap = await self.compute_snapshot()
        if snap is None:
            return False
        try:
            await self._sqlite.insert_equity_snapshot(snap)
            self._last_snapshot_ms = snap["ts_ms"]
            return True
        except Exception as e:
            logger.warning("insert_equity_snapshot failed: %s", e)
            return False

    async def on_position_close(self, realized_pnl: float) -> None:
        """Called by order_manager/close after a close. Writes snapshot."""
        self._realized_today += realized_pnl
        await self.snapshot_once()

    async def run_loop(
        self, shutdown_event: asyncio.Event, has_open_positions_check
    ) -> None:
        """
        Timer loop. Calls snapshot_once every timer_interval_s while
        has_open_positions_check() returns True.
        """
        while not shutdown_event.is_set():
            try:
                has_open = await has_open_positions_check()
                if has_open:
                    await self.snapshot_once()
            except Exception as e:
                logger.warning("equity timer tick failed: %s", e)

            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=self._config.timer_interval_s,
                )
            except asyncio.TimeoutError:
                pass

    def get_realized_today(self) -> float:
        return self._realized_today