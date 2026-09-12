# YAMA Y-331: funding 00/08/16 UTC scheduler ayri task
# YAMA Y-269: _ms int whitelist
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock

"""
FundingMonitor - funding rate monitor and daily loss tracking.

Y-331: funding 00/08/16 UTC scheduler ayri task
Y-269: _ms int whitelist
Y-353: DI
Y-358: asyncio.Lock DI
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.sqlite_writer import SqliteWriter

@dataclass(frozen=True, slots=True)
class FundingMonitorConfig:
    environment: str = "TEST"  # TEST|PROD
    funding_times_utc: tuple[int, int, int] = (0, 8, 16)  # Y-331
    funding_rate_threshold: float = 0.001
    daily_reset_hour_utc: int = 0
    weekly_reset_day: str = "MONDAY"  # weekly MONDAY UTC
    cooldown_ms: int = 3600000

    @property
    def max_daily_loss(self) -> float:
        return -0.04 if self.environment == "TEST" else -0.02

    @property
    def risk_budget(self) -> float:
        return 0.036 if self.environment == "TEST" else 0.018

class FundingMonitor:
    """
    Funding rate monitor with daily loss tracking.

    Y-331: funding 00/08/16 UTC scheduler ayri task
    Y-269: _ms int whitelist
    Y-353: DI
    Y-358: asyncio.Lock DI

    REV5:
      funding UTC 00/08/16
      daily reset UTC
      weekly MONDAY UTC
      max_daily_loss TEST -0.04 / PROD -0.02
      risk math TEST 0.036 / PROD 0.018
    """

    def __init__(
        self,
        config: FundingMonitorConfig,
        sqlite_writer: "SqliteWriter",
        sqlite_lock: asyncio.Lock,  # Y-358 DI
    ) -> None:
        self._config = config
        self._sqlite = sqlite_writer
        self._sqlite_lock = sqlite_lock
        self._daily_pnl: float = 0.0
        self._funding_rates: dict[str, float] = {}

    async def check_funding_time(self, current_hour_utc: int) -> bool:
        """
        Check if current hour is funding time.

        Y-331: funding 00/08/16 UTC.
        Returns True if current_hour_utc in funding_times_utc.
        """
        raise NotImplementedError("FAZ 4")

    async def record_funding_rate(self, symbol: str, rate: float, timestamp_ms: int) -> None:
        """
        Record funding rate for symbol.

        Y-331: funding rate storage.
        """
        raise NotImplementedError("FAZ 4")

    async def get_funding_rate(self, symbol: str) -> float | None:
        """Get last funding rate for symbol."""
        raise NotImplementedError("FAZ 4")

    async def check_daily_loss(self) -> tuple[bool, float]:
        """
        Daily loss check.

        Returns (allowed, remaining).
        TEST -0.04 / PROD -0.02, daily reset UTC, weekly MONDAY UTC.
        """
        raise NotImplementedError("FAZ 4")

    async def update_daily_pnl(self, pnl: float) -> None:
        """Update daily PnL tracking."""
        raise NotImplementedError("FAZ 4")

    async def reset_daily(self) -> None:
        """
        Reset daily tracking.

        Daily reset UTC, weekly MONDAY UTC.
        """
        raise NotImplementedError("FAZ 4")