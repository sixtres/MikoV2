# YAMA Y-305: aging (age_bonus ile effective prio dususu)
# YAMA Y-322a: statik priority heap + heappush
# YAMA Y-322b: CRITICAL full (maxsize 200) fail-fast RuntimeError
# YAMA Y-327: pop while loop, recursion YASAK
# YAMA Y-328: heappush, heapify YASAK (heappush serbest, heapify yasak)
# YAMA Y-330: per-priority min-spacing (2/20/50 ms)
# YAMA Y-343: CRITICAL nominal 2ms max 5ms emergency tolere
# YAMA Y-347: lock altinda heappop/heappush, lock disi sleep(0)
# YAMA Y-355: _last_dispatch[base_prio] - effective degil base_prio

"""
Pacer - priority heap + per-priority spacing + aging.
"""

from __future__ import annotations

import asyncio
import heapq
import itertools
import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

logger = logging.getLogger(__name__)

class PacerPriority(IntEnum):
    CRITICAL = 0
    NORMAL = 1
    REBUILD = 2

@dataclass(frozen=True, slots=True)
class PacerConfig:
    critical_spacing_ms: int = 2
    normal_spacing_ms: int = 20
    rebuild_spacing_ms: int = 50
    critical_maxsize: int = 200

@dataclass(order=True, slots=True)
class _PacerItem:
    base_prio: int
    seq: int
    enqueue_ts: float = field(compare=False)
    payload: Any = field(compare=False)

class Pacer:
    def __init__(self, config: PacerConfig) -> None:
        self._config = config
        self._heap: list[_PacerItem] = []
        self._seq = itertools.count()
        self._lock: asyncio.Lock = asyncio.Lock()
        self._last_dispatch: dict[int, float] = {0: 0.0, 1: 0.0, 2: 0.0}
        self._min_delay: dict[int, float] = {
            0: config.critical_spacing_ms / 1000.0,
            1: config.normal_spacing_ms / 1000.0,
            2: config.rebuild_spacing_ms / 1000.0,
        }

    async def enqueue(self, base_prio: int, payload: Any) -> None:
        assert base_prio in (0, 1, 2), "pacer_priority 0/1/2 distinct"
        async with self._lock:
            if base_prio == 0 and len(self._heap) >= self._config.critical_maxsize:
                raise RuntimeError("CRITICAL pacer full - emergency fallback")
            item = _PacerItem(
                base_prio=base_prio,
                seq=next(self._seq),
                enqueue_ts=time.time(),
                payload=payload,
            )
            heapq.heappush(self._heap, item)

    async def pop(self) -> Any | None:
        while True:
            result = None
            wait = False
            async with self._lock:
                if not self._heap:
                    return None
                item = heapq.heappop(self._heap)
                base_prio = item.base_prio
                age_bonus = int((time.time() - item.enqueue_ts) // 1)
                if age_bonus < 0:
                    age_bonus = 0
                effective = max(0, min(2, base_prio - age_bonus))
                if effective < base_prio:
                    new_item = _PacerItem(
                        base_prio=effective,
                        seq=item.seq,
                        enqueue_ts=item.enqueue_ts,
                        payload=item.payload,
                    )
                    heapq.heappush(self._heap, new_item)
                    wait = True
                else:
                    now = time.monotonic()
                    since = now - self._last_dispatch[base_prio]
                    gap = self._min_delay[effective] - since
                    if gap > 0:
                        heapq.heappush(self._heap, item)
                        wait = True
                    else:
                        self._last_dispatch[base_prio] = now
                        result = item.payload
            if wait:
                await asyncio.sleep(0)
                continue
            return result

    def qsize(self) -> int:
        return len(self._heap)

    def is_empty(self) -> bool:
        return len(self._heap) == 0