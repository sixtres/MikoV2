# YAMA Y-353: DI, no global
# REV8: bulk metrics fetcher + filter + score

"""
Bulk metrics fetcher - single REST call returns ~1184 symbols.
Filters by liquidity, scores by opportunity, returns top N.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .mexc_rest import MEXCRestClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FetcherConfig:
    min_oi_usd: float = 1_000_000.0       # 5M -> 1M
    min_volume24_usd: float = 10_000_000.0  # 50M -> 10M
    min_spread_bps: float = 0.3           # 1.0 -> 0.3            
    max_spread_bps: float = 20.0
    top_n: int = 20
    weight_volume: float = 0.4
    weight_oi: float = 0.3
    weight_funding: float = 0.3    


@dataclass(frozen=True, slots=True)
class RankedSymbol:
    symbol: str
    last_price: float
    volume24_usd: float
    oi_usd: float
    spread_bps: float
    funding_rate: float
    score: float


class BulkMetricsFetcher:
    def __init__(
        self,
        rest: "MEXCRestClient",
        config: FetcherConfig,
        contract_sizes: dict[str, float],
    ) -> None:
        self._rest = rest
        self._cfg = config
        self._contract_sizes = contract_sizes

    @staticmethod
    def _spread_bps(bid: float, ask: float) -> float:
        if bid <= 0 or ask <= 0:
            return 9999.0
        mid = (bid + ask) / 2.0
        if mid <= 0:
            return 9999.0
        return (ask - bid) / mid * 10_000.0

    async def fetch_and_rank(self) -> list[RankedSymbol]:
        raw = await self._rest.fetch_all_tickers()
        cfg = self._cfg
        candidates: list[RankedSymbol] = []

        for item in raw:
            sym = item["symbol"]
            cs = self._contract_sizes.get(sym)
            if cs is None or cs <= 0:
                continue
            last = item["last_price"]
            hold = item["hold_vol"]
            if last <= 0 or hold <= 0:
                continue
            oi_usd = hold * cs * last
            if oi_usd < cfg.min_oi_usd:
                continue
            vol = item["amount24"]
            if vol < cfg.min_volume24_usd:
                continue
            spread = self._spread_bps(item["bid1"], item["ask1"])
            if spread < cfg.min_spread_bps or spread > cfg.max_spread_bps:
                continue
            candidates.append(RankedSymbol(
                symbol=sym,
                last_price=last,
                volume24_usd=vol,
                oi_usd=oi_usd,
                spread_bps=spread,
                funding_rate=item["funding_rate"],
                score=0.0,
            ))

        if not candidates:
            return []

        # normalize for scoring
        max_vol = max(s.volume24_usd for s in candidates) or 1.0
        max_oi = max(s.oi_usd for s in candidates) or 1.0

        scored: list[RankedSymbol] = []
        for s in candidates:
            vol_norm = s.volume24_usd / max_vol
            oi_norm = s.oi_usd / max_oi
            # funding extreme: abs value, capped at 0.005 (0.5%)
            f_abs = min(abs(s.funding_rate) / 0.005, 1.0)
            score = (
                cfg.weight_volume * vol_norm
                + cfg.weight_oi * oi_norm
                + cfg.weight_funding * f_abs
            )
            scored.append(RankedSymbol(
                symbol=s.symbol,
                last_price=s.last_price,
                volume24_usd=s.volume24_usd,
                oi_usd=s.oi_usd,
                spread_bps=s.spread_bps,
                funding_rate=s.funding_rate,
                score=score,
            ))

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[: cfg.top_n]