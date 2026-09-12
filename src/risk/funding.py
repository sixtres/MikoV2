# YAMA Y-331: funding 00/08/16 UTC
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock DI

"""
Funding monitor - funding times 00/08/16 UTC, daily reset, threshold.

Y-331: funding 00/08/16 UTC daily task.
Y-353: DI.
Y-358: asyncio.Lock DI.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.sqlite_writer import SqliteWriter

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class FundingMonitorConfig:
    environment: str = "TEST"
    funding_times_utc: tuple[int,...] = (0, 8, 16)
    funding_rate_threshold: float = 0.001
    daily_reset_hour_utc: int = 0
    weekly_reset_day: str = "MONDAY"
    cooldown_ms: int = 3600000

class FundingMonitor:
    def __init__(
        self,
        config: FundingMonitorConfig,
        sqlite_writer: "SqliteWriter",
        sqlite_lock: asyncio.Lock,
    ) -> None:
        self._config = config
        self._sqlite = sqlite_writer
        self._lock = sqlite_lock
        self._funding_rates: dict[str, dict] = {}
        self._daily_pnl: float = 0.0
        self._last_reset_ms: int = int(time.time() * 1000)

    @property
    def max_daily_loss(self) -> float:
        if self._config.environment == "TEST":
            return -0.04
        return -0.02

    @property
    def risk_budget(self) -> float:
        return abs(self.max_daily_loss)

    async def check_funding_time(self, current_hour_utc: int) -> bool:
        async with self._lock:
            return current_hour_utc in self._config.funding_times_utc

    async def record_funding_rate(self, symbol: str, rate: float, timestamp_ms: int) -> None:
        async with self._lock:
            try:
                self._funding_rates[symbol] = {"rate": rate, "ts": timestamp_ms}
                try:
                    await self._sqlite.execute_wal(
                        {
                            "position_id": symbol,
                            "avg": rate,
                            "original_planned_entry": rate,
                            "version": 0,
                        }
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.warning("record_funding_rate failed symbol=%s error=%s", symbol, e)

    async def get_funding_rate(self, symbol: str) -> float | None:
        async with self._lock:
            entry = self._funding_rates.get(symbol)
            if entry is None:
                return None
            return float(entry.get("rate", 0.0))

    async def check_daily_loss(self) -> tuple[bool, float]:
        async with self._lock:
            try:
                pnl = self._daily_pnl
                if pnl <= self.max_daily_loss:
                    return False, pnl
                return True, pnl
            except Exception as e:
                logger.warning("check_daily_loss failed: %s", e)
                return True, 0.0

    async def update_daily_pnl(self, pnl: float) -> None:
        async with self._lock:
            try:
                self._daily_pnl += pnl
            except Exception as e:
                logger.warning("update_daily_pnl failed: %s", e)

    async def reset_daily(self) -> None:
        async with self._lock:
            try:
                self._daily_pnl = 0.0
                self._last_reset_ms = int(time.time() * 1000)
                logger.warning("daily pnl reset hour=%d", self._config.daily_reset_hour_utc)
            except Exception as e:
                logger.warning("reset_daily failed: %s", e)