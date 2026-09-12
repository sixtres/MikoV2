# YAMA Y-258: R:R 1.4999 net fee taker/maker ayri, PARTIAL_CLOSED
# YAMA Y-260: slippage min(0.03, 0.10/leverage)
# YAMA Y-315: sealed TTL 300s
# YAMA Y-353: DI

"""
FillModel - backtest fill simulation.

Y-258: R:R 1.4999, Taker Depth, PARTIAL_CLOSED, latency max(0, normal(100,50))
Y-260: slippage min(0.03, 0.10/leverage)
Y-315: sealed TTL 300s
Y-353: DI, no global instance
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

class FillStatus(str, Enum):
    FILLED = "FILLED"
    PARTIAL_CLOSED = "PARTIAL_CLOSED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

@dataclass(frozen=True, slots=True)
class FillModelConfig:
    fee_taker: float = 0.0002
    fee_maker: float = 0.0
    fee_fallback: float = 0.0003
    leverage: int = 5
    latency_mean_ms: float = 100.0
    latency_std_ms: float = 50.0
    sealed_ttl_ms: int = 300000  # Y-315 300s
    rr_min: float = 1.4999  # Y-258
    depth_levels: int = 10

    @property
    def slippage_pct(self) -> float:
        """Y-260: min(0.03, 0.10/leverage)."""
        return min(0.03, 0.10 / self.leverage)

@dataclass(slots=True)
class FillResult:
    status: FillStatus
    filled_qty: Decimal
    filled_price: Decimal
    fee: Decimal
    latency_ms: int
    reason: str = ""

class FillModel:
    """
    Backtest fill model.

    Y-258: R:R 1.4999 net fee, taker/maker separate, PARTIAL_CLOSED.
    Taker Depth simulation, latency max(0, normal(100,50)).
    Y-315: sealed TTL 300s
    Y-260: slippage
    Y-353: DI
    """

    def __init__(
        self,
        config: FillModelConfig,
    ) -> None:
        self._config = config

    def compute_fill(
        self,
        side: str,
        qty: Decimal,
        price: Decimal,
        depth: list[tuple[Decimal, Decimal]],
    ) -> FillResult:
        """
        Compute fill against depth.

        Y-258: Taker Depth, PARTIAL_CLOSED if insufficient depth.
        latency = max(0, normal(100,50))
        R:R >= 1.4999 net fee.
        """
        raise NotImplementedError("FAZ 9")

    def check_rr(
        self,
        entry: Decimal,
        tp: Decimal,
        sl: Decimal,
        fee_taker: Decimal,
        fee_maker: Decimal,
    ) -> tuple[bool, Decimal]:
        """
        Y-258: R:R 1.4999 check.

        net_reward = abs(tp-entry) - fee_taker*entry - fee_maker*tp
        net_risk = abs(entry-sl) + fee_taker*entry + fee_maker*tp
        return (rr >= 1.4999, rr)
        """
        raise NotImplementedError("FAZ 9")

    def apply_slippage(self, price: Decimal, side: str) -> Decimal:
        """Apply slippage based on slippage_pct Y-260."""
        raise NotImplementedError("FAZ 9")

    def sample_latency(self) -> int:
        """
        Sample latency: max(0, normal(100,50)).
        Y-258: latency model.
        """
        raise NotImplementedError("FAZ 9")

    def is_sealed_expired(self, sealed_at_ms: int, now_ms: int) -> bool:
        """
        Y-315: sealed TTL 300s check.

        Returns True if now - sealed_at > sealed_ttl_ms.
        """
        raise NotImplementedError("FAZ 9")