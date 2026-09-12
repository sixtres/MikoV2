# YAMA Y-266: SIGTERM 30s grace + tasks pop
# YAMA Y-331: funding_scheduler ayri task
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock DI

"""
Supervisor - funding_scheduler, SIGTERM grace.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SupervisorConfig:
    backoff_ms: tuple[int, int, int, int] = (5000, 10000, 30000, 60000)
    sigterm_grace_s: int = 30
    funding_times_utc: tuple[int, int, int] = (0, 8, 16)


class Supervisor:
    def __init__(
        self,
        config: SupervisorConfig,
        dashboard_app: object,
        funding_monitor: object,
        sqlite_writer: object,
        sqlite_lock: asyncio.Lock,
    ) -> None:
        self._config = config
        self._dashboard = dashboard_app
        self._funding = funding_monitor
        self._sqlite = sqlite_writer
        self._lock = sqlite_lock
        self._shutdown_event = asyncio.Event()
        self._tasks: list = []

    async def run(self) -> None:
        logger.warning("supervisor run start")
        try:
            dash_task = asyncio.create_task(self._dashboard.start())
            fund_task = asyncio.create_task(
                self._run_with_backoff(self.funding_scheduler)
            )
            self._tasks = [dash_task, fund_task]
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self._cleanup()

    async def funding_scheduler(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break

    async def _handle_sigterm(self) -> None:
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=float(self._config.sigterm_grace_s),
            )
        except asyncio.TimeoutError:
            logger.warning("sigterm grace expired")

    async def _run_with_backoff(
        self, coro_func: Callable[..., Awaitable[None]], *args
    ) -> None:
        attempt = 0
        backoff = self._config.backoff_ms
        while not self._shutdown_event.is_set():
            try:
                await coro_func(*args)
                return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("backoff attempt=%d err=%s", attempt, e)
                delay_ms = backoff[min(attempt, len(backoff) - 1)]
                attempt += 1
                try:
                    await asyncio.sleep(delay_ms / 1000.0)
                except asyncio.CancelledError:
                    return

    def stop(self) -> None:
        self._shutdown_event.set()

    async def _cleanup(self) -> None:
        for t in self._tasks:
            if not t.done():
                t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning("cleanup task error: %s", e)
        self._tasks.clear()
        try:
            await self._dashboard.stop()
        except Exception as e:
            logger.warning("dashboard stop failed: %s", e)