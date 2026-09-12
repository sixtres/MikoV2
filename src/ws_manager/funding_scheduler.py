# YAMA Y-331: funding 00/08/16 UTC scheduler ayri asyncio task, supervisor TaskGroup
# YAMA Y-269: all _ms fields int, jitter +-20%
# YAMA Y-353: Stateless - no global mutable
# YAMA Y-358: asyncio.Lock for scheduler state

"""
Funding rate scheduler.

Schedules funding rate fetches at UTC 00/08/16 with jitter.
- Y-331: funding 00/08/16 UTC scheduler separate task, supervisor TaskGroup
- Y-269: all _ms fields int, jitter +-20%
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class FundingSchedulerConfig:
    funding_interval_ms: int = 28800000
    funding_jitter_pct: int = 20

class FundingScheduler:
    """
    Funding scheduler with _ms int and jitter.

    Y-331: funding 00/08/16 UTC scheduler ayri asyncio task, supervisor TaskGroup
    Y-269: _ms int fields, jitter +-20% (aligned to next 00/08/16 UTC boundary)
    """

    def __init__(self, config: FundingSchedulerConfig) -> None:
        self._config = config
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start funding fetch loop - aligns to next 00/08/16 UTC boundary."""
        raise NotImplementedError("FAZ 2")

    async def stop(self) -> None:
        """
        Stop funding loop.

        Y-266: pending tasks must pop in done_callback try/finally.
        Y-311: no task leak.
        """
        raise NotImplementedError("FAZ 2")

    async def _loop(self) -> None:
        """Internal loop with jitter, aligned to 00/08/16 UTC."""
        raise NotImplementedError("FAZ 2")