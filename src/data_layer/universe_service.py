# YAMA Y-353: DI, no global
# REV8: universe service - direct fetcher ranking (scanner disabled for now)

"""
Universe service - direct use of BulkMetricsFetcher ranking.
Scanner hysteresis deferred to a later iteration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .constants import EXCLUDED_SYMBOLS
from .metrics_fetcher import BulkMetricsFetcher, FetcherConfig, RankedSymbol

if TYPE_CHECKING:
    from .mexc_rest import MEXCRestClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScanResult:
    top5: list[str]
    top10: list[str]
    top20: list[str]
    ranked: list[RankedSymbol]
    excluded_symbols: list[str]


class UniverseService:
    def __init__(
        self,
        rest: "MEXCRestClient",
        fetcher_config: FetcherConfig,
        contract_sizes: dict[str, float],
        always_include: tuple[str, ...] = ("BTC_USDT",),
        excluded_symbols: frozenset[str] = EXCLUDED_SYMBOLS,
    ) -> None:
        # §6.2: exclude -- always_include ile cakisirsa exclude kazanir
        safe_always = tuple(s for s in always_include if s not in excluded_symbols)
        if len(safe_always) != len(always_include):
            dropped = sorted(set(always_include) - set(safe_always))
            logger.warning("EXCLUDED_SYMBOL_IN_ALWAYS_INCLUDE symbols=%s", dropped)
        self._fetcher = BulkMetricsFetcher(
            rest,
            fetcher_config,
            contract_sizes,
            excluded_symbols=excluded_symbols,
        )
        self._always = safe_always
        self._excluded = excluded_symbols
        self._last_result: ScanResult | None = None

    async def scan(self) -> ScanResult:
        ranked = await self._fetcher.fetch_and_rank()
        ordered: list[str] = list(self._always)
        for r in ranked:
            if r.symbol not in ordered:
                ordered.append(r.symbol)

        top5 = ordered[:5]
        top10 = ordered[:10]
        top20 = ordered[:20]

        result = ScanResult(
            top5=top5,
            top10=top10,
            top20=top20,
            ranked=ranked,
            excluded_symbols=sorted(self._excluded),
        )
        self._last_result = result
        return result

    @property
    def last_result(self) -> ScanResult | None:
        return self._last_result