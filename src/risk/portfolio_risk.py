# YAMA Y-258: R:R 1.4999 net fee taker/maker
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock DI
# FIX Y-258 REV5: taker entry'ye, maker tp'ye ayri

"""
Portfolio risk - TEST/PROD risk params, RR net fee, second entry size.

Y-258: RR 1.4999 net fee taker/maker REV5 total_fee = entry*fee_taker + tp*fee_maker.
Y-353: DI no global.
Y-358: asyncio.Lock DI.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.sqlite_writer import SqliteWriter

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class PortfolioRiskConfig:
    environment: str = "TEST"
    position_mode: str = "ONE_WAY"
    margin_mode: str = "ISOLATED"
    target_leverage: int = 5
    max_sl_distance: float = 0.025
    correlation_threshold: float = 0.85
    correlation_window_ms: int = 3600000
    correlation_min_samples: int = 30
    size_mult_second: float = 0.5
    cooldown_ms: int = 3600000

class PortfolioRiskManager:
    def __init__(
        self,
        config: PortfolioRiskConfig,
        sqlite_writer: "SqliteWriter",
        sqlite_lock: asyncio.Lock,
    ) -> None:
        self._config = config
        self._sqlite = sqlite_writer
        self._lock = sqlite_lock
        self._daily_pnl = Decimal("0")

    @property
    def risk_per_trade(self) -> float:
        if self._config.environment == "TEST":
            return 0.008
        return 0.006

    @property
    def max_positions(self) -> int:
        if self._config.environment == "TEST":
            return 3
        return 2

    @property
    def max_daily_loss(self) -> float:
        if self._config.environment == "TEST":
            return -0.04
        return -0.02

    def compute_rr(
        self,
        entry: Decimal,
        tp: Decimal,
        sl: Decimal,
        fee_taker: Decimal,
        fee_maker: Decimal,
    ) -> Decimal:
        try:
            if tp > entry:
                gross_profit = tp - entry
                gross_loss = entry - sl
            else:
                gross_profit = entry - tp
                gross_loss = sl - entry

            if gross_loss <= Decimal("0"):
                return Decimal("0")

            # FIX Y-258 REV5: taker entry'ye, maker tp'ye AYRI
            total_fee = entry * fee_taker + tp * fee_maker
            net_profit = gross_profit - total_fee
            net_loss = gross_loss + total_fee

            if net_loss <= Decimal("0"):
                return Decimal("0")

            rr = net_profit / net_loss
            return rr
        except Exception as e:
            logger.warning("compute_rr failed entry=%s error=%s", entry, e)
            return Decimal("0")

    async def check_new_position(
        self, symbol: str, side: str, qty: Decimal, price: Decimal
    ) -> tuple[bool, str]:
        async with self._lock:
            try:
                rows = await self._sqlite.fetch(
                    "SELECT COUNT(*) FROM positions WHERE emergency_pending=0"
                )
                count = int(rows[0][0]) if rows and rows[0] else 0
            except Exception:
                count = 0

            if count >= self.max_positions:
                return False, "MAX_POSITIONS_EXCEEDED"

            return True, "OK"

    async def check_second_entry(self, position_id: str, correlation_same_id: bool) -> bool:
        async with self._lock:
            if not correlation_same_id:
                return False
            try:
                rows = await self._sqlite.fetch(
                    "SELECT position_id FROM positions WHERE position_id=?",
                    (position_id,),
                )
                if not rows:
                    return False
                return True
            except Exception as e:
                logger.warning("check_second_entry failed id=%s err=%s", position_id, e)
                return False

    async def check_daily_loss(self) -> tuple[bool, Decimal]:
        async with self._lock:
            try:
                pnl = self._daily_pnl
                limit = Decimal(str(self.max_daily_loss))
                if pnl <= limit:
                    return False, pnl
                return True, pnl
            except Exception as e:
                logger.warning("check_daily_loss failed: %s", e)
                return True, Decimal("0")