# YAMA Y-275: token bucket acquire before snapshot fetch - rate 8 burst 15
# YAMA Y-313: single epoch increment after snapshot
# YAMA Y-353: Stateless - no global mutable

"""
Snapshot fetcher.

Fetches L2 snapshot via REST with token bucket guard.
- Acquire bucket before fetch (Y-275)
- Single epoch increment (Y-313)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..data_layer.l2_buffer import L2Book, L2Buffer
    from ..data_layer.token_bucket import TokenBucket

@dataclass(frozen=True, slots=True)
class SnapshotConfig:
    rest_url: str
    depth: int = 1000
    rest_outer_timeout_ms: int = 3500

class SnapshotFetcher:
    """
    Snapshot fetcher with token bucket guard.

    Y-275: acquire before fetch
    Y-313: single epoch increment
    """

    def __init__(
        self,
        config: SnapshotConfig,
        token_bucket: "TokenBucket",
        books: dict[str, "L2Book"],
        l2_buffer: "L2Buffer",
    ) -> None:
        """
        Initialize snapshot fetcher.

        Args:
            config: Snapshot config with rest_outer_timeout_ms (Y-269).
            token_bucket: Token bucket rate 8 burst 15 (Y-275).
            books: per-symbol L2Book dict via DI (Y-353).
            l2_buffer: applied after fetch, uses its own RLock (Y-253).
        """
        self._config = config
        self._token_bucket = token_bucket
        self._books = books
        self._l2_buffer = l2_buffer

    async def fetch(self, symbol: str) -> Any:
        """
        Fetch snapshot for symbol.

        Token bucket acquire (Y-275) before REST call.
        """
        raise NotImplementedError("FAZ 2")

    async def fetch_and_apply(self, symbol: str) -> bool:
        """
        Fetch snapshot and apply to L2Buffer.

        Returns True if applied, False on error.
        Single epoch increment (Y-313).
        """
        raise NotImplementedError("FAZ 2")