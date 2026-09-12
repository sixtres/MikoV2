# YAMA Y-266: SIGTERM 30s grace
# YAMA Y-331: funding_scheduler ayri task
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock DI

"""
Supervisor - TaskGroup, funding_scheduler ayri task, backoff, SIGTERM 30s grace.

Y-266: SIGTERM 30s grace
Y-331: funding_scheduler ayri task (00/08/16 UTC)
Y-353: DI
Y-358: asyncio.Lock DI
"""

from __future__ import annotations

import asyncio
import signal
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from .storage.sqlite_writer import SqliteWriter
    from .dashboard.app import DashboardApp
    from .risk.funding import FundingMonitor

@dataclass(frozen=True, slots=True)
class SupervisorConfig:
    backoff_ms: tuple[int, int, int, int] = (5000, 10000, 30000, 60000)
    sigterm_grace_s: int = 30
    funding_times_utc: tuple[int, int, int] = (0, 8, 16)

class Supervisor:
    """
    Supervisor with TaskGroup.

    TaskGroup, funding_scheduler ayri task (Y-331),
    backoff [5000,10000,30000,60000], SIGTERM 30s grace (Y-266).
    Y-353: DI
    """

    def __init__(
        self,
        config: SupervisorConfig,
        dashboard_app: "DashboardApp",
        funding_monitor: "FundingMonitor",
        sqlite_writer: "SqliteWriter",
        sqlite_lock: asyncio.Lock,
    ) -> None:
        self._config = config
        self._dashboard_app = dashboard_app
        self._funding_monitor = funding_monitor
        self._sqlite = sqlite_writer
        self._sqlite_lock = sqlite_lock
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def run(self) -> None:
        """
        Run supervisor.

        TaskGroup ile tum tasklari yonet, funding_scheduler ayri task.
        backoff [5000,10000,30000,60000], SIGTERM 30s grace.
        """
        raise NotImplementedError("FAZ 9")

    async def funding_scheduler(self) -> None:
        """
        Funding scheduler separate task.

        Y-331: funding 00/08/16 UTC scheduler ayri task.
        """
        raise NotImplementedError("FAZ 9")

    async def _handle_sigterm(self) -> None:
        """
        SIGTERM handler with 30s grace.

        Y-266: SIGTERM 30s grace.
        """
        raise NotImplementedError("FAZ 9")

    async def _run_with_backoff(
        self,
        coro_func: Callable[..., Awaitable[None]],
        *args,
    ) -> None:
        """
        Run coroutine with backoff [5000,10000,30000,60000].
        """
        raise NotImplementedError("FAZ 9")

    def stop(self) -> None:
        """Trigger graceful shutdown."""
        raise NotImplementedError("FAZ 9")