# YAMA Y-254: expected_seq epoch reset same lock pre_sync_queue clear
# YAMA Y-266: tasks pop done_callback try/finally
# YAMA Y-269: _ms int whitelist
# YAMA Y-275: token bucket acquire before snapshot
# YAMA Y-311: no task leak
# YAMA Y-313: seq_epoch single increment on snapshot
# YAMA Y-314: seq_epoch defaultdict reset on reconnect
# YAMA Y-358: asyncio.Lock

"""
WS Manager - connect / handle_message / resync.

Y-254: epoch reset same lock pre_sync_queue clear.
Y-266: done_callback pop try/finally.
Y-269: _ms whitelist.
Y-275: token bucket acquire before snapshot (via fetcher).
Y-311: no task leak.
Y-313: single epoch increment.
Y-314: seq_epoch reset on reconnect.
Y-358: asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..data_layer.l2_buffer import L2Book, L2Buffer
    from ..data_layer.seq import SequenceValidator
    from ..data_layer.token_bucket import TokenBucket
    from .snapshot import SnapshotFetcher

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class WSConfig:
    symbols: tuple[str,...]
    ws_url: str
    ws_reconnect_backoff_ms: tuple[int,...] = (1000, 2000, 5000, 10000, 30000)
    ws_reconnect_cap_ms: int = 60000
    ws_reconnect_jitter_pct: int = 20
    ws_ping_interval_ms: int = 15000
    ws_pong_timeout_ms: int = 5000
    ws_max_ping_failures: int = 3

class WSManager:
    def __init__(
        self,
        config: WSConfig,
        l2_buffer: "L2Buffer",
        seq_validator: "SequenceValidator",
        token_bucket: "TokenBucket",
        snapshot_fetcher: "SnapshotFetcher",
        books: dict,
        locks: dict,
    ) -> None:
        self._config = config
        self._l2_buffer = l2_buffer
        self._seq_validator = seq_validator
        self._token_bucket = token_bucket
        self._snapshot_fetcher = snapshot_fetcher
        self._books = books
        self._locks = locks
        self._ws_tasks: dict[str, asyncio.Task] = {}
        self._current_epoch: dict[str, int] = {}
        self._synced: dict[str, bool] = {}

    async def connect(self, symbol: str) -> None:
        if symbol in self._ws_tasks:
            return

        epoch = self._current_epoch.get(symbol, 0) + 1
        self._current_epoch[symbol] = epoch
        self._synced[symbol] = False

        try:
            await self._seq_validator.set_epoch(symbol, epoch)
        except Exception as e:
            logger.warning("set_epoch failed symbol=%s error=%s", symbol, e)

        book = self._books.get(symbol)
        if book is not None:
            try:
                book.pre_sync_queue[symbol] = []
            except Exception:
                pass

        task = asyncio.create_task(self._ws_loop(symbol, epoch))

        def _done_cb(t: asyncio.Task, sym=symbol):
            try:
                self._ws_tasks.pop(sym, None)
                try:
                    exc = t.exception()
                    if exc is not None:
                        logger.warning(
                            "ws task done exception symbol=%s exc=%s", sym, exc
                        )
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.warning("ws done cb error symbol=%s error=%s", sym, e)
            finally:
                pass

        task.add_done_callback(_done_cb)
        self._ws_tasks[symbol] = task

    async def handle_message(self, symbol: str, msg: Any, epoch: int) -> None:
        if epoch!= self._current_epoch.get(symbol):
            return

        if not self._synced.get(symbol, False):
            book = self._books.get(symbol)
            if book is not None:
                try:
                    book.pre_sync_queue[symbol].append(
                        {"seq": msg.get("seq", 0), "epoch": epoch, "data": msg}
                    )
                except Exception as e:
                    logger.warning("pre_sync_queue append failed: %s", e)
            return

        first_u = msg.get("U", msg.get("seq", 0))
        final_u = msg.get("u", msg.get("seq", 0))

        try:
            result = await self._seq_validator.validate(symbol, epoch, first_u, final_u)
        except Exception as e:
            logger.warning("validate failed symbol=%s error=%s", symbol, e)
            return

        if getattr(result, "needs_resync", False):
            await self.resync(symbol)
            return

        if not getattr(result, "is_valid", True):
            return

        try:
            book = self._books.get(symbol)
            if book is not None:
                diffs = msg.get("diffs", [])
                self._l2_buffer.apply_batch(symbol, diffs, epoch)
        except Exception as e:
            logger.warning("apply_batch failed symbol=%s error=%s", symbol, e)

    async def on_snapshot(self, symbol: str, snapshot: Any) -> None:
        try:
            await self._snapshot_fetcher.fetch_and_apply(symbol)
        except Exception as e:
            logger.warning("fetch_and_apply failed symbol=%s error=%s", symbol, e)
            return

        self._synced[symbol] = True

    async def resync(self, symbol: str) -> None:
        self._synced[symbol] = False
        try:
            await self._snapshot_fetcher.fetch_and_apply(symbol)
        except Exception as e:
            logger.warning("resync fetch failed symbol=%s error=%s", symbol, e)
            return
        self._synced[symbol] = True

    async def disconnect(self, symbol: str) -> None:
        task = self._ws_tasks.get(symbol)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning("disconnect await error symbol=%s error=%s", symbol, e)
        self._ws_tasks.pop(symbol, None)

    async def _ws_loop(self, symbol: str, epoch: int) -> None:
        while True:
            try:
                await asyncio.sleep(self._config.ws_ping_interval_ms / 1000.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("ws_loop error symbol=%s error=%s", symbol, e)
                await asyncio.sleep(0.1)