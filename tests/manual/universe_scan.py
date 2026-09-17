"""
Manual universe scan against live MEXC data.

Usage:
    python -m tests.manual.universe_scan
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.data_layer.metrics_fetcher import FetcherConfig
from src.data_layer.mexc_rest import MEXCRestClient
from src.data_layer.universe_scanner import ScannerConfig, UniverseScanner
from src.data_layer.universe_service import UniverseService


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        rest = MEXCRestClient(session)
        scanner = UniverseScanner(ScannerConfig(
            max_top=5, max_watch=10,
            always_include=("BTC_USDT",),
            min_oi_usd=5_000_000.0,
        ))
        svc = UniverseService(rest, scanner, FetcherConfig(top_n=20))
        result = await svc.scan()

        print("=== Top 5 ===")
        for s in result.top5:
            print("  ", s)
        print()
        print("=== Top 20 ranked ===")
        for r in result.ranked[:20]:
            print("  %-12s  score=%.4f  vol=$%.1fM  oi=$%.1fM  "
                  "spread=%.2fbps  funding=%.5f%%" % (
                      r.symbol, r.score,
                      r.volume24_usd / 1e6, r.oi_usd / 1e6,
                      r.spread_bps, r.funding_rate * 100))
        print()
        print("counts:", result.counts)


if __name__ == "__main__":
    asyncio.run(main())