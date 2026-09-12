# YAMA Y-265: sealed_lock ayri (fill_lock'tan)
# YAMA Y-315: OrderedDict TTL 300s, dict value {sealed_at_local_ms, exchange_ts_ms, version}
# YAMA Y-336: exchange_ts_ms None guard
# YAMA Y-353: DI, no global
# YAMA Y-354: TTL cleanup full scan, break YASAK
# YAMA Y-358: asyncio.Lock (sealed_lock DI)
# YAMA Y-361: exchange_ts age check
# YAMA Y-365: Y-354 redundant absorption (KEEP)

"""
Sealed store - duplicate fill prevention via TTL tracked order ids.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SealedStoreConfig:
    seal_ttl_ms: int = 300000
    exchange_ts_tolerance_ms: int = 2000

class SealedStore:
    def __init__(
        self,
        config: SealedStoreConfig,
        sealed_lock: asyncio.Lock,
    ) -> None:
        self._config = config
        self._sealed_lock = sealed_lock
        self._sealed_orders: OrderedDict[str, dict] = OrderedDict()

    async def seal(
        self,
        order_id: str,
        sealed_at_local_ms: int,
        exchange_ts_ms: int | None,
        version: int,
    ) -> None:
        async with self._sealed_lock:
            self._sealed_orders[order_id] = {
                "sealed_at_local_ms": sealed_at_local_ms,
                "exchange_ts_ms": exchange_ts_ms,
                "version": version,
            }

    async def is_sealed(
        self, order_id: str, incoming_exchange_ts: int
    ) -> bool:
        async with self._sealed_lock:
            entry = self._sealed_orders.get(order_id)
            if entry is None:
                return False
            exch_ts = entry.get("exchange_ts_ms")
            if exch_ts is not None:
                if incoming_exchange_ts < exch_ts - self._config.exchange_ts_tolerance_ms:
                    return True
            return True

    async def cleanup_expired(self) -> int:
        now_ms = int(time.time() * 1000)
        removed = 0
        async with self._sealed_lock:
            # Y-354: full scan, no break
            for oid in list(self._sealed_orders.keys()):
                entry = self._sealed_orders[oid]
                local_expired = (
                    now_ms - entry["sealed_at_local_ms"]
                ) > self._config.seal_ttl_ms
                exch_ts = entry.get("exchange_ts_ms")
                exch_expired = (
                    exch_ts is not None
                    and (now_ms - exch_ts) > self._config.seal_ttl_ms
                )
                # Y-365: redundant absorption, KEEP
                if local_expired or exch_expired:
                    self._sealed_orders.pop(oid, None)
                    removed += 1
        return removed

    def size(self) -> int:
        return len(self._sealed_orders)

    def clear(self) -> None:
        self._sealed_orders.clear()