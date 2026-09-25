# YAMA Y-353: DI, no global
# REV8: bulk metrics fetcher + filter + score

"""
Bulk metrics fetcher - single REST call returns ~1184 symbols.
Filters by liquidity, scores by opportunity, returns top N.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .mexc_rest import MEXCRestClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FetcherConfig:
    min_oi_usd: float = 1_000_000.0
    min_volume24_usd: float = 10_000_000.0
    min_spread_bps: float = 0.3
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
        excluded_symbols: frozenset[str] = frozenset(),
    ) -> None:
        self._rest = rest
        self._cfg = config
        self._contract_sizes = contract_sizes
        # §6.2: emtia/hisse token exclude (DI ile gelir; default bos)
        self._excluded = excluded_symbols

    def update_contract_sizes(self, sizes: dict[str, float]) -> None:
        """B3.5-SORU 1=B: bulk fetch sonrası eksik anahtarları doldur.

        DI ile gelen değerler öncelikli; mevcut anahtarlar ezilmez.
        Caller intent kazanır (UniverseService DI + bulk merge).
        """
        for sym, cs in sizes.items():
            if sym not in self._contract_sizes:
                self._contract_sizes[sym] = cs

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
            # §6.2: exclude -- skorlama ve normalizasyondan once ele
            if sym in self._excluded:
                continue
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

        max_vol = max(s.volume24_usd for s in candidates) or 1.0
        max_oi = max(s.oi_usd for s in candidates) or 1.0

        scored: list[RankedSymbol] = []
        for s in candidates:
            vol_norm = s.volume24_usd / max_vol
            oi_norm = s.oi_usd / max_oi
            # §6.1: asiri funding (> %0.5) ceza; aksi halde dogrusal skor
            f_abs = abs(s.funding_rate)
            if f_abs > 0.005:
                f_score = -1.0
            else:
                f_score = f_abs / 0.005
            score = (
                cfg.weight_volume * vol_norm
                + cfg.weight_oi * oi_norm
                + cfg.weight_funding * f_score
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