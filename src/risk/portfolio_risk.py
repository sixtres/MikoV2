# YAMA Y-258: R:R 1.4999 net fee taker/maker ayri
# YAMA Y-301: position_mode_side ONE_WAY belirsiz fix -> BOTH
# YAMA Y-323: Decimal quantize str(Decimal), float YASAK
# YAMA Y-36: position_mode ONE_WAY required
# YAMA Y-37: margin_mode ISOLATED default
# YAMA Y-38: target_leverage 5
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock DI

"""
PortfolioRiskManager - portfolio level risk checks.

Y-258: R:R 1.4999 net fee taker/maker ayri
Y-301: position_mode_side ONE_WAY -> BOTH
Y-323: Decimal quantize, no float
Y-36: position_mode ONE_WAY required
Y-37: margin_mode ISOLATED default
Y-38: target_leverage 5
Y-353: DI
Y-358: asyncio.Lock DI

REV5:
  risk math TEST 0.036 / PROD 0.018
  correlation window 1h min 30 hedge
  bias majority
  second entry bypass same id
  max SL 2.5%
  funding UTC 00/08/16
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.sqlite_writer import SqliteWriter

@dataclass(frozen=True, slots=True)
class PortfolioRiskConfig:
    environment: str = "TEST"  # TEST|PROD
    position_mode: str = "ONE_WAY"  # Y-36
    margin_mode: str = "ISOLATED"  # Y-37
    target_leverage: int = 5  # Y-38
    max_sl_distance: float = 0.025  # max SL 2.5%
    correlation_threshold: float = 0.85
    correlation_window_ms: int = 3600000  # 1h
    correlation_min_samples: int = 30
    size_mult_second: float = 0.5
    cooldown_ms: int = 3600000

    @property
    def risk_per_trade(self) -> float:
        return 0.008 if self.environment == "TEST" else 0.006

    @property
    def max_positions(self) -> int:
        return 3 if self.environment == "TEST" else 2

    @property
    def max_daily_loss(self) -> float:
        return -0.04 if self.environment == "TEST" else -0.02

class PortfolioRiskManager:
    """
    Portfolio risk manager.

    Y-258: R:R 1.4999 net fee taker/maker
    Y-301: position_mode_side ONE_WAY -> BOTH
    Y-323: Decimal quantize, float YASAK
    Y-36: position_mode required
    Y-37: margin_mode ISOLATED
    Y-353: DI
    Y-358: asyncio.Lock DI

    REV5:
      risk math TEST 0.036 / PROD 0.018
      correlation window 1h min 30 hedge
      bias majority
      second entry bypass same id
      max SL 2.5%
      funding UTC 00/08/16
    """

    def __init__(
        self,
        config: PortfolioRiskConfig,
        sqlite_writer: "SqliteWriter",
        sqlite_lock: asyncio.Lock,  # Y-358 DI
    ) -> None:
        self._config = config
        self._sqlite = sqlite_writer
        self._sqlite_lock = sqlite_lock
        self._exposure_by_symbol: dict[str, Decimal] = {}

    async def check_new_position(
        self, symbol: str, side: str, qty: Decimal, price: Decimal
    ) -> tuple[bool, str]:
        """
        Check if new position allowed.

        Returns (allowed, reason):
          - bias majority check
          - max positions (TEST 3 / PROD 2)
          - max daily loss
          - correlation directional
          - max SL 2.5%
        Y-323: Decimal math, no float.
        """
        raise NotImplementedError("FAZ 4")

    async def check_second_entry(
        self, position_id: str, correlation_same_id: bool
    ) -> bool:
        """
        Second entry bypass.

        Same id bypass, correlation check skipped if correlation_same_id.
        """
        raise NotImplementedError("FAZ 4")

    def compute_rr(
        self, entry: Decimal, tp: Decimal, sl: Decimal, fee_taker: Decimal, fee_maker: Decimal
    ) -> Decimal:
        """
        Y-258: R:R with net fee.

        net_reward = abs(tp - entry) - fee_taker*entry - fee_maker*tp
        net_risk = abs(entry - sl) + fee_taker*entry + fee_maker*tp
        return net_reward / net_risk
        Must be >= 1.4999
        """
        raise NotImplementedError("FAZ 4")

    async def check_daily_loss(self) -> tuple[bool, Decimal]:
        """
        Daily loss check.

        Returns (allowed, remaining). TEST -0.04 / PROD -0.02.
        Y-323: Decimal, no float.
        """
        raise NotImplementedError("FAZ 4")