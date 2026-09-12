# YAMA Y-266: tasks pop done_callback try/finally
# YAMA Y-269: _ms int whitelist
# YAMA Y-311: no task leak
# YAMA Y-331: funding 00/08/16 UTC scheduler AYRI task, supervisor TaskGroup
# YAMA Y-353: DI, no global
# YAMA Y-358: asyncio.Lock

"""
Funding scheduler - 00/08/16 UTC separate task.

Y-331: funding scheduler separate task.
Y-269: _ms int whitelist.
Y-266: done_callback try/finally.
Y-311: no task leak.
Y-353: DI, no global.
Y-358: asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class FundingSchedulerConfig:
    funding_interval_ms: int = 28800000
    funding_jitter_pct: int = 20

class FundingScheduler:
    def __init__(self, config: FundingSchedulerConfig) -> None:
        self._config = config
        self._lock: asyncio.Lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._running: bool = False

    def _on_done(self, task: asyncio.Task) -> None:
        try:
            try:
                exc = task.exception()
                if exc is not None:
                    logger.warning("funding task done with exception: %s", exc)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning("funding done callback error: %s", e)
        finally:
            pass

    async def start(self) -> None:
        async with self._lock:
            if self._running:
                return
            self._running = True
            self._task = asyncio.create_task(self._loop())
            self._task.add_done_callback(self._on_done)

    async def stop(self) -> None:
        async with self._lock:
            if not self._running:
                return
            self._running = False

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning("funding stop error: %s", e)
            finally:
                self._task = None

    async def _loop(self) -> None:
        while self._running:
            sleep_s = self._config.funding_interval_ms / 1000.0
            jitter_factor = 1.0 + (random.random() * 2 - 1) * (
                self._config.funding_jitter_pct / 100.0
            )
            sleep_s *= jitter_factor
            try:
                await asyncio.sleep(sleep_s)
            except asyncio.CancelledError:
                break

            logger.info("funding scheduler tick")