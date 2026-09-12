# YAMA Y-258: R:R 1.4999 net fee
# YAMA Y-260: slippage = min(0.03, 0.10/leverage)
# YAMA Y-283: FLIP tespitinde emergency_close zorunlu
# YAMA Y-289: ONE_WAY positionSide BOTH
# YAMA Y-291: dust false-positive CLOSED_DUST YASAK
# YAMA Y-295: FLIP fill_lock deadlock fix lock disina cik
# YAMA Y-297: retry + filled_by_order advance after commit
# YAMA Y-302: dust <min_lot -> DUST_ACKNOWLEDGED
# YAMA Y-315: sealed_orders TTL 300s
# YAMA Y-323: Decimal quantize str(Decimal) ROUND_DOWN
# YAMA Y-339/350: fill(2)->sqlite(3)->pacer(4)->flush(5)
# YAMA Y-353: DI
# YAMA Y-358: fill_lock DI

"""
Order manager - fill event handling, slippage, quantize.

Y-260: slippage min(0.03, 0.10/leverage).
Y-283: FLIP emergency_close.
Y-291/Y-302: dust DUST_ACKNOWLEDGED.
Y-295: FLIP outside fill_lock.
Y-297: retry + advance after commit.
Y-323: Decimal quantize.
Y-353: DI.
Y-358: fill_lock DI.
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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
                    order_id = row[0]
                    filled_qty = float(row[1])
                    self._filled_by_order[order_id] = filled_qty
                except Exception as e:
                    logger.warning("on_startup row parse failed: %s", e)
                    continue

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

            if existing!= 0 and (existing > 0)!= (fill_qty > 0):
                flip_detected = True
            else:
                new_fill = max(existing, fill_qty) if existing!= 0 else fill_qty
                inc = new_fill - existing
                if inc <= 0:
                    return

        if flip_detected:
            try:
                await self._rest.emergency_close(order_id)
            except Exception as e:
                logger.warning("emergency_close on FLIP failed: %s", e)
            return

        epsilon = self._config.min_lot / self._config.epsilon_divisor
        if abs(fill_qty) < epsilon:
            logger.warning(
                "DUST_ACKNOWLEDGED order_id=%s qty=%f", order_id, fill_qty
            )
            return

        for attempt in range(self._config.max_retry):
            async with self._fill_lock:
                existing = self._filled_by_order.get(order_id, 0.0)
                new_fill = max(existing, fill_qty) if existing!= 0 else fill_qty
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
                    return
                except Exception as e:
                    logger.warning(
                        "versioned update attempt %d failed: %s", attempt, e
                    )
                    continue

        logger.warning("on_fill_event max retry exhausted order_id=%s", order_id)

    def leverage_adjusted_slippage(self) -> float:
        return min(0.03, 0.10 / self._config.leverage)

    def quantize_qty(self, qty: float, precision: int) -> str:
        from decimal import ROUND_DOWN, Decimal

        d = Decimal(str(qty))
        q = Decimal("1").scaleb(-precision)
        return str(d.quantize(q, rounding=ROUND_DOWN))