# YAMA Y-260: slippage = min(0.03, 0.10/leverage) decimal, not bps
# YAMA Y-283: FLIP tespitinde emergency_close zorunlu
# YAMA Y-289: ONE_WAY positionSide "BOTH" zorunlu
# YAMA Y-291: dust false-positive CLOSED_DUST YASAK
# YAMA Y-295: FLIP fill_lock deadlock fix lock disina cik
# YAMA Y-297: retry + filled_by_order advance after commit
# YAMA Y-302: dust <min_lot DUST_ACKNOWLEDGED
# YAMA Y-315: sealed_orders TTL 300s dict value {sealed_at_local_ms, exchange_ts_ms, version}
# YAMA Y-323: Decimal quantize str(Decimal) ROUND_DOWN
# YAMA Y-339: lock hierarchy fill_lock(2)->sqlite(3)->pacer(4)
# YAMA Y-350: sqlite(3)->pacer(4)->flush(5)
# YAMA Y-353: DI, no global
# YAMA Y-358: asyncio.Lock (fill_lock DI)

"""
OrderManager - order lifecycle and fill tracking.

Y-260: slippage = min(0.03, 0.10/leverage)
Y-283: FLIP detection -> emergency_close
Y-289: ONE_WAY positionSide BOTH
Y-291: dust false-positive CLOSED_DUST forbidden
Y-295: FLIP deadlock fix
Y-297: advance filled_by_order after commit only
Y-302: dust < min_lot DUST_ACKNOWLEDGED
Y-315: sealed_orders TTL
Y-323: Decimal quantize str(Decimal) ROUND_DOWN
Y-339/350: lock hierarchy fill(2)->sqlite(3)->pacer(4)->flush(5)
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..storage.sqlite_writer import SqliteWriter
    from ..storage.sealed import SealedStore
    from .rest_gateway import RestGateway

@dataclass(frozen=True, slots=True)
class OrderManagerConfig:
    max_retry: int = 3 # Y-285
    leverage: int = 5 # position target
    min_lot: float = 0.001 # Y-302
    epsilon_divisor: float = 2.0 # min_lot/2

class OrderManager:
    """
    Order lifecycle and fill tracking.

    Y-260: slippage = min(0.03, 0.10/leverage) decimal
    Y-283: FLIP tespitinde emergency_close zorunlu
    Y-289: ONE_WAY positionSide BOTH zorunlu
    Y-291: dust false-positive CLOSED_DUST YASAK
    Y-295: FLIP fill_lock deadlock fix lock disina cik
    Y-297: retry + filled_by_order advance after commit
    Y-302: dust <min_lot DUST_ACKNOWLEDGED
    Y-315: sealed_orders TTL 300 dict value {sealed_at_local_ms, exchange_ts_ms, version}
    Y-323: Decimal quantize str(Decimal) ROUND_DOWN
    Y-339: lock hierarchy fill(2)->sqlite(3)->pacer(4)
    Y-350: sqlite(3)->pacer(4)->flush(5)
    Y-353: DI, no global
    Y-358: asyncio.Lock (fill_lock DI)
    """

    def __init__(
        self,
        config: OrderManagerConfig,
        fill_lock: asyncio.Lock, # Y-339
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
        """
        Recover partial fills from DB.

        Y-297: startup sync under fill_lock.
        Y-323: no float, Decimal via str() for recovery math.
        """
        raise NotImplementedError("FAZ 4")

    async def on_fill_event(
        self,
        order_id: str,
        fill_qty: float,
        fill_price: float,
        exchange_ts_ms: int,
        position_id: str,
    ) -> None:
        """
        Handle fill event.

        Y-283: if sign(fill) != sign(existing): FLIP -> emergency_close outside lock
        Y-289: fills tracked with monotonic max(existing, new)
        Y-291: dust <min_lot*0.1 -> DUST_ACKNOWLEDGED, no CLOSED_DUST false-positive
        Y-295: FLIP emergency_close called OUTSIDE fill_lock (no deadlock)
        Y-297: retry loop max 3 versioned update, advance filled_by_order ONLY after commit
        Y-302: dust <min_lot -> DUST_ACKNOWLEDGED
        Y-315: sealed check/update via sealed_store
        Y-323: qty via Decimal quantize
        Y-339/350: fill(2)->sqlite(3)->pacer(4)->flush(5) hierarchy
        """
        raise NotImplementedError("FAZ 4")

    def leverage_adjusted_slippage(self) -> float:
        """
        Y-260: min(0.03, 0.10/leverage).

        20x -> min(0.03, 0.005) = 0.005
        5x  -> min(0.03, 0.02)  = 0.02
        30x -> min(0.03, 0.0033)= 0.0033

        Returns decimal, not bps.
        """
        raise NotImplementedError("FAZ 4")

    def quantize_qty(self, qty: float, precision: int) -> str:
        """
        Y-323: Decimal quantize str(Decimal) ROUND_DOWN.

        str(Decimal) not Decimal(float) to avoid binary float artifact.
        """
        raise NotImplementedError("FAZ 4")