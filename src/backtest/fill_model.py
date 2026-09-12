# YAMA Y-258: R:R 1.4999 net fee taker/maker
# YAMA Y-260: slippage = min(0.03, 0.10/leverage)
# YAMA Y-315: sealed TTL 300s
# YAMA Y-323: Decimal quantize str(Decimal) ROUND_DOWN
# YAMA Y-353: DI

"""
Backtest fill model - taker depth simulation, R:R net fee, latency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
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
    sealed_ttl_ms: int = 300000
    rr_min: float = 1.4999
    depth_levels: int = 10

    @property
    def slippage_pct(self) -> float:
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
    def __init__(self, config: FillModelConfig) -> None:
        self._config = config

    def compute_fill(
        self,
        side: str,
        qty: Decimal,
        price: Decimal,
        depth: list[tuple[Decimal, Decimal]],
    ) -> FillResult:
        if qty <= Decimal("0"):
            return FillResult(
                status=FillStatus.REJECTED,
                filled_qty=Decimal("0"),
                filled_price=Decimal("0"),
                fee=Decimal("0"),
                latency_ms=0,
                reason="ZERO_QTY",
            )

        if not depth:
            return FillResult(
                status=FillStatus.REJECTED,
                filled_qty=Decimal("0"),
                filled_price=Decimal("0"),
                fee=Decimal("0"),
                latency_ms=0,
                reason="EMPTY_DEPTH",
            )

        remaining = qty
        total_cost = Decimal("0")
        total_filled = Decimal("0")

        levels = depth[: self._config.depth_levels]
        for level_price, level_qty in levels:
            if remaining <= Decimal("0"):
                break
            if level_qty <= Decimal("0"):
                continue
            take = min(remaining, level_qty)
            total_cost += take * level_price
            total_filled += take
            remaining -= take

        if total_filled == Decimal("0"):
            return FillResult(
                status=FillStatus.REJECTED,
                filled_qty=Decimal("0"),
                filled_price=Decimal("0"),
                fee=Decimal("0"),
                latency_ms=0,
                reason="NO_LIQUIDITY",
            )

        avg_price = total_cost / total_filled
        avg_price = self.apply_slippage(avg_price, side)
        avg_price = self._quantize(avg_price, 8)

        fee_rate = Decimal(str(self._config.fee_taker))
        fee = self._quantize(avg_price * total_filled * fee_rate, 8)
        latency = self.sample_latency()

        if remaining > Decimal("0"):
            status = FillStatus.PARTIAL_CLOSED
            reason = "INSUFFICIENT_DEPTH"
        else:
            status = FillStatus.FILLED
            reason = ""

        return FillResult(
            status=status,
            filled_qty=total_filled,
            filled_price=avg_price,
            fee=fee,
            latency_ms=latency,
            reason=reason,
        )

    def check_rr(
        self,
        entry: Decimal,
        tp: Decimal,
        sl: Decimal,
        fee_taker: Decimal,
        fee_maker: Decimal,
    ) -> tuple[bool, Decimal]:
        # Y-258 REV5: total_fee = entry*fee_taker + tp*fee_maker
        total_fee = entry * fee_taker + tp * fee_maker
        gross_profit = abs(tp - entry)
        gross_loss = abs(entry - sl)

        if gross_loss <= Decimal("0"):
            return False, Decimal("0")

        net_profit = gross_profit - total_fee
        net_loss = gross_loss + total_fee

        if net_loss <= Decimal("0"):
            return False, Decimal("0")

        rr = net_profit / net_loss
        passes = rr >= Decimal(str(self._config.rr_min))
        return passes, rr

    def apply_slippage(self, price: Decimal, side: str) -> Decimal:
        slippage = Decimal(str(self._config.slippage_pct))
        s = side.lower()
        if s in ("buy", "long", "bid"):
            return price * (Decimal("1") + slippage)
        return price * (Decimal("1") - slippage)

    def sample_latency(self) -> int:
        try:
            val = random.normalvariate(
                self._config.latency_mean_ms, self._config.latency_std_ms
            )
        except Exception:
            val = self._config.latency_mean_ms
        return max(0, int(val))

    def is_sealed_expired(self, sealed_at_ms: int, now_ms: int) -> bool:
        return (now_ms - sealed_at_ms) > self._config.sealed_ttl_ms

    @staticmethod
    def _quantize(value: Decimal, precision: int) -> Decimal:
        q = Decimal("1").scaleb(-precision)
        return value.quantize(q, rounding=ROUND_DOWN)