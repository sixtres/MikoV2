# YAMA Y-254: expected_seq epoch reset same lock pre_sync_queue clear
# YAMA Y-275: rate 8 burst 15 - token bucket acquire before snapshot
# YAMA Y-269: ws reconnect _ms int, jitter +-20%, ping/pong config
# YAMA Y-313: seq_epoch single increment on snapshot
# YAMA Y-314: seq_epoch defaultdict, expected_seq, _seq_lock
# YAMA Y-353: Stateless - no global mutable, deps via DI
# YAMA Y-358: asyncio.Lock for manager state

"""
WebSocket manager.

Manages L2 streams per symbol with epoch handling.
- seq_epoch reset on reconnect same lock pre_sync_queue clear (Y-254)
- pre_sync_queue clear under same _seq_lock (Y-254)
- token bucket acquire before snapshot (Y-275)
- on_snapshot single epoch increment (Y-313)
- ws reconnect _ms int, jitter +-20%, ping/pong (Y-269)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..data_layer.l2_buffer import L2Book, L2Buffer
    from ..data_layer.seq import SequenceValidator
    from ..data_layer.token_bucket import TokenBucket
    from .snapshot import SnapshotFetcher

@dataclass(frozen=True, slots=True)
class WSConfig:
    symbols: tuple[str, ...]
    ws_url: str
    ws_reconnect_backoff_ms: tuple[int, ...] = (1000, 2000, 5000, 10000, 30000)
    ws_reconnect_cap_ms: int = 60000
    ws_reconnect_jitter_pct: int = 20
    ws_ping_interval_ms: int = 15000
    ws_pong_timeout_ms: int = 5000
    ws_max_ping_failures: int = 3

class WSManager:
    """
    WS manager with epoch and queue handling.

    Y-254: epoch reset + pre_sync_queue clear same lock
    Y-275: token bucket rate 8 burst 15
    Y-313: seq_epoch single increment
    Y-314: per-symbol seq_epoch, expected_seq, pre_sync_queue
    Y-269: _ms int backoff, jitter +-20%, ping/pong config
    """

    def __init__(
        self,
        config: WSConfig,
        l2_buffer: "L2Buffer",
        seq_validator: "SequenceValidator",
        token_bucket: "TokenBucket",
        snapshot_fetcher: "SnapshotFetcher",
        books: dict[str, "L2Book"],
        locks: dict[str, asyncio.Lock],
    ) -> None:
        """
        Initialize WS manager.

        Args:
            config: WS config with _ms int fields (Y-269).
            l2_buffer: L2 buffer via DI.
            seq_validator: Sequence validator via DI.
            token_bucket: Token bucket rate 8 burst 15 (Y-275).
            snapshot_fetcher: Snapshot fetcher.
            books: per-symbol L2Book dict via DI (Y-353).
            _locks: per-symbol asyncio.Lock (Y-358) for connection state and
                sync boundary. L2Buffer has its own RLock (Y-253) for buffer
                mutation - these are distinct locks for distinct state.
        """
        self._config = config
        self._l2_buffer = l2_buffer
        self._seq_validator = seq_validator
        self._token_bucket = token_bucket
        self._snapshot_fetcher = snapshot_fetcher
        self._books = books
        self._locks = locks

    async def connect(self, symbol: str) -> None:
        """Connect WS for symbol - epoch reset on reconnect (Y-254)."""
        raise NotImplementedError("FAZ 2")

    async def handle_message(self, symbol: str, msg: Any, epoch: int) -> None:
        """
        Handle incoming L2 message.

        If not synced: append to pre_sync_queue (Y-352).
        If synced: validate seq epoch (Y-254) and apply batch.
        """
        raise NotImplementedError("FAZ 2")

    async def on_snapshot(self, symbol: str, snapshot: Any) -> None:
        """
        Apply snapshot, single epoch increment, clear pre_sync_queue (Y-313, Y-314).

        Same lock for epoch reset + queue clear (Y-254).
        Token bucket acquire before fetch (Y-275).
        """
        raise NotImplementedError("FAZ 2")

    async def resync(self, symbol: str) -> None:
        """Trigger re-sync - token bucket acquire + snapshot fetch."""
        raise NotImplementedError("FAZ 2")

    async def disconnect(self, symbol: str) -> None:
        """
        Disconnect WS for symbol.
        Y-266: pending tasks must pop in done_callback try/finally.
        Y-311: no task leak.
        """
        raise NotImplementedError("FAZ 2")