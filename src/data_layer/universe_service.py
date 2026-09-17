# YAMA Y-353: DI, no global
# REV8: universe service - fetcher + scanner glue

"""
Universe service - combines BulkMetricsFetcher + UniverseScanner.
Single entry point for "which symbols should we trade now".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .metrics_fetcher import BulkMetricsFetcher, FetcherConfig, RankedSymbol
from .universe_scanner import (
    SymbolMetrics,
    UniverseScanner,
    UniverseStatus,
)

if TYPE_CHECKING:
    from .mexc_rest import MEXCRestClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScanResult:
    top5: list[str]
    top10: list[str]
    top20: list[str]
    counts: dict
    ranked: list[RankedSymbol]


class UniverseService:
    def __init__(
        self,
        rest: "MEXCRestClient",
        scanner: UniverseScanner,
        fetcher_config: FetcherConfig,
    ) -> None:
        self._fetcher = BulkMetricsFetcher(rest, fetcher_config)
        self._scanner = scanner
        self._last_result: ScanResult | None = None

    async def scan(self) -> ScanResult:
        ranked = await self._fetcher.fetch_and_rank()

        # adapt to scanner's expected format
        scanner_metrics: list[SymbolMetrics] = []
        for r in ranked:
            scanner_metrics.append(SymbolMetrics(
                symbol=r.symbol,
                oi_change=0.0,
                liq=0.0,
                squeeze=0.0,
                funding=min(abs(r.funding_rate) / 0.005, 1.0),
                spread_bps=r.spread_bps,
                oi_usd=r.oi_usd,
            ))

        self._scanner.refresh(scanner_metrics)

        top5 = self._scanner.get_top5()
        active = self._scanner.get_active_symbols()
        top10 = active[:10]
        top20 = [r.symbol for r in ranked[:20]]

        counts = self._scanner.status_counts()

        result = ScanResult(
            top5=top5,
            top10=top10,
            top20=top20,
            counts=counts,
            ranked=ranked,
        )
        self._last_result = result
        return result

    @property
    def last_result(self) -> ScanResult | None:
        return self._last_result