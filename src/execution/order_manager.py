# YAMA Y-258, Y-260, Y-283, Y-289, Y-291, Y-295, Y-297, Y-302, Y-315, Y-323
# YAMA Y-339/350, Y-353, Y-358
# REV7: DB lifecycle (open_position + close_position + qty_remaining)

"""
Order manager - fill event handling + DB lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.sealed import SealedStore
    from ..storage.sqlite_writer import SqliteWriter
    from .rest_gateway import RestGateway

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OrderManagerConfig:
    max_retry: int = 3
    leverage: int = 5
    min_lot: float = 0.001
    epsilon_divisor: float = 2.0


class OrderManager:
    def __init__(
        self,
        config: OrderManagerConfig,
        fill_lock: asyncio.Lock,
        sqlite_writer: "SqliteWriter",
        sealed_store: "SealedStore",
        rest_gateway: "RestGateway",
    ) -> None:
        self._config = config
        self._fill_lock = fill_lock
        self._sqlite = sqlite_writer
        self._sealed = sealed_store
        self._rest = rest_gateway
        self._filled_by_order: dict[str, float] = {}
        self._position_by_order: dict[str, str] = {}
        self._position_opened: set[str] = set()
        self._position_side: dict[str, str] = {}
        self._position_symbol: dict[str, str] = {}
        self._position_avg: dict[str, float] = {}
        self._position_orig_entry: dict[str, float] = {}
        self._position_orig_sl: dict[str, float] = {}
        self._position_qty_open: dict[str, float] = {}
        self._position_universe: dict[str, str] = {}
        self._position_whale_trust: dict[str, int] = {}

    # ------------------------------------------------------------- registration

    def register_position(
        self,
        position_id: str,
        symbol: str,
        side: str,
        universe_status: str = "UNKNOWN",
        whale_trust_score: int = 0,
    ) -> None:
        """Called by caller when position opens (before fills arrive)."""
        self._position_side[position_id] = side
        self._position_symbol[position_id] = symbol
        self._position_universe[position_id] = universe_status
        self._position_whale_trust[position_id] = whale_trust_score

    # ------------------------------------------------------------- startup

    async def on_startup(self) -> None:
        async with self._fill_lock:
            try:
                rows = await self._sqlite.fetch(
                    "SELECT order_id, filled_qty FROM orders WHERE status='PARTIAL'"
                )
            except Exception as e:
                logger.warning("on_startup fetch failed: %s", e)
                return
            for row in rows or []:
                try:
                    self._filled_by_order[row[0]] = float(row[1])
                except Exception:
                    continue

    # ------------------------------------------------------------- fill event

    async def on_fill_event(
        self,
        order_id: str,
        fill_qty: float,
        fill_price: float,
        exchange_ts_ms: int,
        position_id: str,
    ) -> None:
        flip_detected = False

        async with self._fill_lock:
            existing = self._filled_by_order.get(order_id, 0.0)
            if math.isclose(fill_qty, 0.0, abs_tol=1e-9):
                return
            if existing != 0 and (existing > 0) != (fill_qty > 0):
                flip_detected = True
            else:
                new_fill = max(existing, fill_qty) if existing != 0 else fill_qty
                inc = new_fill - existing
                if inc <= 0:
                    return

        if flip_detected:
            try:
                await self._rest.emergency_close(order_id)
            except Exception as e:
                logger.warning("emergency_close on FLIP failed: %s", e)
            # DB close with reason FLIP
            try:
                await self._sqlite.close_position(
                    position_id=position_id,
                    close_reason="FLIP",
                    realized_pnl=0.0,
                    fee_total=0.0,
                    r_multiple=None,
                )
            except Exception as e:
                logger.warning("close_position FLIP failed: %s", e)
            return

        epsilon = self._config.min_lot / self._config.epsilon_divisor
        if abs(fill_qty) < epsilon:
            logger.warning("DUST_ACKNOWLEDGED order_id=%s qty=%f", order_id, fill_qty)
            return

        for attempt in range(self._config.max_retry):
            async with self._fill_lock:
                existing = self._filled_by_order.get(order_id, 0.0)
                new_fill = max(existing, fill_qty) if existing != 0 else fill_qty
                inc = new_fill - existing
                if inc <= 0:
                    return
                try:
                    current_version = await self._sqlite.get_version(position_id)
                    await self._sqlite.update_position_versioned(
                        position_id,
                        fill_price,
                        fill_price,
                        fill_price,
                        current_version + 1,
                    )
                    self._filled_by_order[order_id] = new_fill
                    self._position_by_order[order_id] = position_id
                    break
                except Exception as e:
                    logger.warning(
                        "versioned update attempt %d failed: %s", attempt, e
                    )
                    continue
        else:
            logger.warning(
                "on_fill_event max retry exhausted order_id=%s", order_id
            )
            return

        # ---- DB: open position on first fill ----
        if position_id not in self._position_opened:
            symbol = self._position_symbol.get(position_id, "UNKNOWN")
            side = self._position_side.get(position_id, "LONG")
            now_ms = int(time.time() * 1000)
            try:
                await self._sqlite.open_position(
                    {
                        "position_id": position_id,
                        "symbol": symbol,
                        "side": side,
                        "opened_at_ms": now_ms,
                        "avg": fill_price,
                        "qty_open": abs(fill_qty),
                        "qty_remaining": abs(fill_qty),
                        "original_planned_entry": fill_price,
                        "original_tp": fill_price,
                        "original_sl": fill_price,
                        "current_tp_shifted": fill_price,
                        "current_sl_shifted": fill_price,
                        "whale_trust_score": self._position_whale_trust.get(
                            position_id, 0
                        ),
                        "universe_status": self._position_universe.get(
                            position_id, "UNKNOWN"
                        ),
                        "version": 0,
                    }
                )
                self._position_opened.add(position_id)
                self._position_avg[position_id] = fill_price
                self._position_orig_entry[position_id] = fill_price
                self._position_orig_sl[position_id] = fill_price
                self._position_qty_open[position_id] = abs(fill_qty)
            except Exception as e:
                logger.warning("open_position DB failed: %s", e)

    # ------------------------------------------------------------- helpers

    def leverage_adjusted_slippage(self) -> float:
        return min(0.03, 0.10 / self._config.leverage)

    def quantize_qty(self, qty: float, precision: int) -> str:
        d = Decimal(str(qty))
        q = Decimal("1").scaleb(-precision)
        return str(d.quantize(q, rounding=ROUND_DOWN))