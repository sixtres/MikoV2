# YAMA Y-265: sealed_lock ayri (fill_lock'tan)
# YAMA Y-315: sealed_orders OrderedDict TTL 300s, value {sealed_at_local_ms, exchange_ts_ms, version}
# YAMA Y-336: exchange_ts_ms None guard
# YAMA Y-353: DI, no global
# YAMA Y-354: TTL cleanup full scan, break YASAK
# YAMA Y-358: asyncio.Lock (sealed_lock)
# YAMA Y-361: exchange_ts age check (reuse engelle)
# YAMA Y-365: Y-354 redundant absorption notu

"""
SealedStore - sealed_orders OrderedDict for duplicate fill prevention.

Y-265: sealed_lock separate from fill_lock
Y-315: OrderedDict TTL 300s dict value {sealed_at_local_ms, exchange_ts_ms, version}
Y-336: exchange_ts_ms None guard, reuse check
Y-354: TTL cleanup full scan, break FORBIDDEN, OrderedDict insertion != timestamp
Y-358: sealed_lock asyncio.Lock
Y-361: exchange_ts age check
Y-365: redundant absorption kept intentionally (Y-354 condition)
Y-353: DI
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Final

@dataclass(frozen=True, slots=True)
class SealedStoreConfig:
    seal_ttl_ms: int = 300000 # Y-315 300s
    exchange_ts_tolerance_ms: int = 2000 # Y-336 -2s window

class SealedStore:
    """
    Sealed orders store - prevents duplicate fill processing.

    Y-265: sealed_lock separate from fill_lock
    Y-315: OrderedDict TTL 300s, value {sealed_at_local_ms, exchange_ts_ms, version}
    Y-336: exchange_ts_ms None guard
    Y-353: DI
    Y-354: TTL cleanup full scan, break FORBIDDEN (insertion != timestamp)
    Y-358: sealed_lock asyncio.Lock
    Y-361: exchange_ts age check - prevents reuse with old exchange_ts
    Y-365: Y-354 condition has redundant absorption, kept per spec (expired local OR expired exchange)
    """

    def __init__(
        self,
        config: SealedStoreConfig,
        sealed_lock: asyncio.Lock, # Y-265 Y-358
    ) -> None:
        self._config = config
        self._sealed_lock = sealed_lock
        self._sealed_orders: OrderedDict[str, dict[str, Any]] = OrderedDict()

    async def seal(
        self,
        order_id: str,
        sealed_at_local_ms: int,
        exchange_ts_ms: int | None,
        version: int,
    ) -> None:
        """
        Seal an order.

        Y-315: store as dict {sealed_at_local_ms, exchange_ts_ms, version}
        Y-336: exchange_ts_ms may be None (guard on read)
        """
        raise NotImplementedError("FAZ 4")

    async def is_sealed(self, order_id: str, incoming_exchange_ts: int) -> bool:
        """
        Check if order_id is sealed and not expired.

        Y-336: exchange_ts_ms None guard - if sealed entry has None, treat as not sealed for age
        Y-361: incoming_exchange_ts < sealed_exchange_ts - tolerance -> old event, already sealed
               reuse of exchange_ts prevented
        """
        raise NotImplementedError("FAZ 4")

    async def cleanup_expired(self) -> int:
        """
        Full scan TTL cleanup, break FORBIDDEN (Y-354).

        Y-354: OrderedDict insertion order != timestamp order, must scan all, no break early.
        Y-361: local expired (now_ms - sealed_at_local_ms > ttl) OR exchange_ts expired.
        Y-365: condition has redundant absorption (local expired absorbs exchange check partially) - KEEP per spec.

        Returns removed count.
        """
        raise NotImplementedError("FAZ 4")

    def size(self) -> int:
        """Return sealed count."""
        raise NotImplementedError("FAZ 4")

    def clear(self) -> None:
        """Clear all sealed (for tests/reconnect)."""
        raise NotImplementedError("FAZ 4")