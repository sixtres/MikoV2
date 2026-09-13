# REV7: WS->REST mark price cache for equity snapshots
# YAMA Y-353: DI, no global
# YAMA Y-358: asyncio.Lock

"""
Mark price cache - single writer (WS), single reader (equity tracker).

WS process pushes {"symbol": str, "price": float, "ts_ms": int} at 60s
into state_queue. This cache consumes those events and stores last known
mark per symbol.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MarkPriceCache:
    def __init__(self) -> None:
        self._prices: dict[str, float] = {}
        self._timestamps: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def update(self, symbol: str, price: float, ts_ms: int) -> None:
        async with self._lock:
            self._prices[symbol] = float(price)
            self._timestamps[symbol] = int(ts_ms)

    async def get(self, symbol: str) -> float | None:
        async with self._lock:
            return self._prices.get(symbol)

    async def get_with_ts(self, symbol: str) -> tuple[float, int] | None:
        async with self._lock:
            p = self._prices.get(symbol)
            if p is None:
                return None
            return p, self._timestamps.get(symbol, 0)

    async def handle_event(self, event: Any) -> bool:
        """Handle state_queue event. Returns True if it was a mark price."""
        if not isinstance(event, dict):
            return False
        if event.get("type") != "mark_price":
            return False
        symbol = event.get("symbol")
        price = event.get("price")
        if symbol is None or price is None:
            return False
        await self.update(symbol, price, int(event.get("ts_ms", 0)))
        return True

    def size(self) -> int:
        return len(self._prices)