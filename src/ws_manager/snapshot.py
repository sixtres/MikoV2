# YAMA Y-269: rest_outer_timeout_ms whitelist
# YAMA Y-275: token bucket acquire before snapshot fetch
# YAMA Y-313: single epoch increment after snapshot
# YAMA Y-353: DI, no global

"""
Snapshot fetcher - token bucket rate limited, epoch single increment.

Y-275: token bucket acquire before fetch.
Y-313: single epoch increment inside on_snapshot.
Y-269: rest_outer_timeout_ms whitelist.
Y-353: DI, no global.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..data_layer.l2_buffer import L2Book, L2Buffer
    from ..data_layer.token_bucket import TokenBucket

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class SnapshotConfig:
    rest_url: str
    depth: int = 1000
    rest_outer_timeout_ms: int = 3500

class SnapshotFetcher:
    def __init__(
        self,
        config: SnapshotConfig,
        token_bucket: "TokenBucket",
        books: dict,
        l2_buffer: "L2Buffer",
    ) -> None:
        self._config = config
        self._token_bucket = token_bucket
        self._books = books
        self._l2_buffer = l2_buffer

    async def fetch(self, symbol: str) -> Any | None:
        try:
            await self._token_bucket.acquire()
        except Exception as e:
            logger.warning("token bucket acquire failed: %s", e)
            return None

        async def _do_fetch():
            # stub HTTP - real aiohttp later
            # url = %s/depth?symbol=%s&limit=%s % (rest_url, symbol, depth)
            return {"bids": [], "asks": [], "lastUpdateId": 0}

        try:
            timeout_s = self._config.rest_outer_timeout_ms / 1000.0
            result = await asyncio.wait_for(_do_fetch(), timeout=timeout_s)
            return result
        except asyncio.TimeoutError:
            logger.warning("snapshot fetch timeout symbol=%s", symbol)
            return None
        except Exception as e:
            logger.warning("snapshot fetch failed symbol=%s error=%s", symbol, e)
            return None

    async def fetch_and_apply(self, symbol: str) -> bool:
        snapshot = await self.fetch(symbol)
        if snapshot is None:
            return False

        book = self._books.get(symbol)
        if book is None:
            try:
                from ..data_layer.l2_buffer import L2Book

                book = L2Book(symbol=symbol)
                self._books[symbol] = book
            except Exception as e:
                logger.warning("create book failed: %s", e)
                return False

        try:
            self._l2_buffer.on_snapshot(symbol, snapshot)
            return True
        except Exception as e:
            logger.warning("on_snapshot failed symbol=%s error=%s", symbol, e)
            return False