# YAMA Y-276: telemetry DROP_OLDEST 1000, put_nowait DROP
# YAMA Y-329: mp.Queue bridge for process-boundary telemetry
# YAMA Y-353: Stateless - no global mutable, instance via DI

"""
Telemetry queue with DROP_OLDEST.

Process-boundary queue: WS process -> REST gateway -> alerting.
put_nowait is sync - fire-and-forget, never blocks event loop.
"""

from __future__ import annotations

import multiprocessing as mp
from typing import Any

class AsyncTelemetryQueue:
    """
    Telemetry queue with DROP_OLDEST (Y-276).

    Process-boundary queue: WS process -> REST gateway -> alerting.
    put_nowait is sync - fire-and-forget, never blocks event loop.
    DROP_OLDEST on overflow, unlike state_queue (DROP_NEVER).

    Y-276: telemetry DROP_OLDEST 1000, put_nowait DROP
    Y-329: mp.Queue bridge for process-boundary telemetry
    Y-353: instance via DI
    """

    def __init__(self, maxsize: int = 1000) -> None:
        self._maxsize: int = maxsize
        self._q: mp.Queue = mp.Queue(maxsize=maxsize)
        self._dropped: int = 0

    def put_nowait(self, item: Any) -> None:
        """
        Put item, DROP_OLDEST if full (Y-276).

        Sync fire-and-forget. On QueueFull:
          1. get_nowait() to evict oldest
          2. put_nowait() retry
          3. If still full, drop silently + increment counter
        """
        raise NotImplementedError("FAZ 3")

    def get_nowait(self) -> Any:
        """Non-blocking get from mp.Queue. Returns None if empty."""
        raise NotImplementedError("FAZ 3")

    def qsize(self) -> int:
        """Return current queue size."""
        raise NotImplementedError("FAZ 3")

    def dropped_count(self) -> int:
        """Return count of dropped items (Y-276 metric)."""
        raise NotImplementedError("FAZ 3")

    @property
    def maxsize(self) -> int:
        return self._maxsize