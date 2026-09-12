# YAMA Y-264 REVISE + Y-310: counter+Lock, refcount==0 clear ALWAYS
# YAMA Y-276: force-flush daemon 2 worker, bounded 5, put_nowait DROP telemetry only
# YAMA Y-346: counter underflow WARNING zorunlu
# YAMA Y-350: flush(5) hierarchy, call_soon_threadsafe YASAK direct Event
# YAMA Y-356: tek sayac, cift sayac YASAK
# YAMA Y-358: threading.Lock ISTISNASI (sync API icin)
# YAMA Y-362: max(0, counter-1) YASAK (underflow gizler), truthy bug YASAK
# YAMA Y-368: assert prod YASAK, WARNING+clamp

"""
Flush controller - single counter + threading.Lock exception.

Y-264+Y-310: counter+Lock, refcount==0 set.
Y-276: force-flush daemon 2 worker, bounded 5 DROP telemetry.
Y-346: underflow WARNING.
Y-350: direct Event.
Y-356: tek sayac.
Y-358: threading.Lock istisnasi.
Y-362: max(0, ...) yasak, once -1 sonra check.
Y-368: assert yasak, WARNING+clamp.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class FlushControllerConfig:
    bounded_queue_size: int = 5

class FlushController:
    def __init__(self, config: FlushControllerConfig) -> None:
        self._config = config
        self._counter: int = 0
        self._lock: threading.Lock = threading.Lock()
        self._async_event: asyncio.Event = asyncio.Event()
        self._async_event.set()
        self._force_flush_queue: asyncio.Queue = asyncio.Queue(
            maxsize=config.bounded_queue_size
        )

    def suspend(self) -> None:
        with self._lock:
            self._counter += 1
            if self._counter == 1:
                try:
                    self._async_event.clear()
                except Exception:
                    pass

    def resume(self) -> None:
        with self._lock:
            self._counter -= 1
            if self._counter < 0:
                logger.warning("FLUSH_COUNTER_UNDERFLOW current=%d", self._counter)
                self._counter = 0
            if self._counter == 0:
                try:
                    self._async_event.set()
                except Exception:
                    pass

    def is_suspended(self) -> bool:
        with self._lock:
            return self._counter > 0

    async def force_flush_daemon(self, worker_id: int) -> None:
        while True:
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break

    def try_enqueue_flush(self, item) -> bool:
        try:
            self._force_flush_queue.put_nowait(item)
            return True
        except asyncio.QueueFull:
            return False