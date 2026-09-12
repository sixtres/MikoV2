# YAMA Y-322a: Pacer heap statik priority + heappush
# YAMA Y-322b: CRITICAL full queue fail-fast (maxsize 200 CRITICAL)
# YAMA Y-327: Pacer.pop recursion YASAK, while loop zorunlu
# YAMA Y-328: Pacer.enqueue heapq.heappush, heapify YASAK
# YAMA Y-330: min-spacing CRITICAL 2ms NORMAL 20ms REBUILD 50ms (per-priority)
# YAMA Y-343: CRITICAL nominal 2ms max 5ms emergency tolere
# YAMA Y-347: Pacer.pop lock altinda heappop/heappush, lock disi sleep(0)
# YAMA Y-355: _last_dispatch[base_prio] - effective (aging) degil base_prio
# YAMA Y-358: asyncio.Lock (threading.Lock YASAK)
# YAMA Y-353: Stateless - no global mutable, DI
# YAMA Y-269: all _ms fields int

"""
Pacer - rate limiter with priority heap and aging.

Y-322a: heapq.heappush static priority
Y-322b: CRITICAL full (200) fail-fast RuntimeError
Y-327: pop while loop, recursion forbidden
Y-328: heappush, heapify forbidden
Y-330: per-priority min-spacing 2/20/50ms
Y-343: CRITICAL nominal 2ms max 5ms emergency tolerate
Y-347: lock inside heappop/heappush, outside sleep(0)
Y-355: _last_dispatch[base_prio] not effective
"""

from __future__ import annotations

import asyncio
import heapq
import itertools
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

class PacerPriority(Enum):
    CRITICAL = 0
    NORMAL = 1
    REBUILD = 2

@dataclass(frozen=True, slots=True)
class PacerConfig:
    critical_spacing_ms: int = 2
    normal_spacing_ms: int = 20
    rebuild_spacing_ms: int = 50
    critical_maxsize: int = 200 # Y-322b

@dataclass(order=True, slots=True)
class _PacerItem:
    base_prio: int
    seq: int
    enqueue_ts: float = field(compare=False)
    payload: Any = field(compare=False)

class Pacer:
    """
    Rate limiting pacer with priority heap and aging.

    Y-322a: heapq.heappush static priority
    Y-322b: CRITICAL full (200) fail-fast RuntimeError
    Y-327: pop while loop, recursion FORBIDDEN
    Y-328: heappush, heapify FORBIDDEN
    Y-330: per-priority min-spacing
    Y-343: CRITICAL nominal 2ms max 5ms emergency tolerate
    Y-347: lock inside heappop/heappush, outside sleep(0)
    Y-355: _last_dispatch[base_prio] effective not base_prio
    Y-358: asyncio.Lock
    Y-353: stateless via DI
    """

    def __init__(self, config: PacerConfig) -> None:
        self._config = config
        self._heap: list[_PacerItem] = []
        self._seq = itertools.count()
        self._lock: asyncio.Lock = asyncio.Lock() # Y-358
        self._last_dispatch: dict[int, float] = {0: 0.0, 1: 0.0, 2: 0.0} # Y-330
        self._min_delay: dict[int, float] = { # Y-343
            0: config.critical_spacing_ms / 1000.0,
            1: config.normal_spacing_ms / 1000.0,
            2: config.rebuild_spacing_ms / 1000.0,
        }

    async def enqueue(self, base_prio: int, payload: Any) -> None:
        """
        Enqueue item.

        Y-322a: heappush
        Y-322b: if CRITICAL (0) and heap len >= 200: raise RuntimeError
        Y-328: heapify FORBIDDEN, only heappush
        """
        raise NotImplementedError("FAZ 3")

    async def pop(self) -> Any | None:
        """
        Pop next ready item with aging (Y-305).

        Y-327: while loop, recursion FORBIDDEN
        Y-347: lock inside heappop/heappush, outside sleep(0)
        Y-355: _last_dispatch[base_prio] (not effective)

        Aging:
          age_bonus = int((time.time() - item.enqueue_ts) // 1)
          effective = max(0, item.base_prio - age_bonus)
          if effective < base_prio:
             heappush back with effective prio, wait
          gap = _min_delay[effective] - (now - _last_dispatch[base_prio])
          if gap > 0: heappush back, wait
          else: _last_dispatch[base_prio] = now, return payload

        Outside lock asyncio.sleep(0) yield.
        """
        raise NotImplementedError("FAZ 3")

    def qsize(self) -> int:
        """Return heap size."""
        raise NotImplementedError("FAZ 3")

    def is_empty(self) -> bool:
        """Return True if heap empty."""
        raise NotImplementedError("FAZ 3")