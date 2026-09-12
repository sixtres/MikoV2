# YAMA Y-276: telemetry DROP_OLDEST 1000, put_nowait DROP (state DROP_NEVER)
# YAMA Y-329: mp.Queue bridge for process-boundary telemetry
# YAMA Y-353: DI, no global

"""
AsyncTelemetryQueue - telemetry DROP_OLDEST 1000, fire-and-forget sync.

Y-276: telemetry DROP_OLDEST 1000, state DROP_NEVER ayri.
Y-329: mp.Queue bridge for process-boundary telemetry.
Y-353: DI, no global.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import queue

logger = logging.getLogger(__name__)

class AsyncTelemetryQueue:
    def __init__(self, maxsize: int = 1000) -> None:
        self._maxsize = maxsize
        self._q: mp.Queue = mp.Queue(maxsize=maxsize)
        self._dropped: int = 0

    @property
    def maxsize(self) -> int:
        return self._maxsize

    def put_nowait(self, item) -> None:
        try:
            self._q.put_nowait(item)
        except (queue.Full, Exception):
            try:
                self._q.get_nowait()
            except (queue.Empty, Exception):
                pass
            try:
                self._q.put_nowait(item)
            except (queue.Full, Exception):
                self._dropped += 1
                logger.warning("telemetry drop oldest failed, dropped=%d", self._dropped)

    def get_nowait(self):
        try:
            return self._q.get_nowait()
        except (queue.Empty, Exception):
            return None

    def qsize(self) -> int:
        try:
            return self._q.qsize()
        except Exception:
            return 0

    def dropped_count(self) -> int:
        return self._dropped