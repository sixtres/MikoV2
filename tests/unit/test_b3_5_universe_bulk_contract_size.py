# tests/unit/test_b3_5_universe_bulk_contract_size.py
# B3.5-SORU 1=B: UniverseService.scan() ilk cagride bulk contract-size
# fetch yapar; fetcher.update_contract_sizes DI degerlerini korur.
"""Bulk contract-size fetch wiring (B3.5-SORU 1=B)."""
from __future__ import annotations

import asyncio

from src.data_layer.metrics_fetcher import BulkMetricsFetcher, FetcherConfig
from src.data_layer.universe_service import UniverseService


class _FakeRest:
    """fetch_all_contract_details + fetch_all_tickers; cagri sayaci."""

    def __init__(self, bulk: dict[str, float]) -> None:
        self._bulk = bulk
        self.bulk_calls = 0

    async def fetch_all_contract_details(self) -> dict[str, float]:
        self.bulk_calls += 1
        return dict(self._bulk)

    async def fetch_all_tickers(self) -> list[dict]:
        # BTC DI'da var; ETH yalniz bulk'tan gelirse ranklenebilir.
        # oi_usd = hold_vol * cs * last >= 1_000_000 (min_oi_usd) olmali.
        #   BTC: 1_000_000 * 0.0001 * 50000 = 5_000_000 USDT
        #   ETH: 10_000_000 * 0.01  * 3000  = 300_000_000 USDT
        # amount24 >= 10_000_000 (min_volume24_usd); spread 0.3-20 bps.
        return [
            {
                "symbol": "BTC_USDT", "last_price": 50000.0,
                "bid1": 49999.0, "ask1": 50001.0,
                "hold_vol": 1_000_000.0,
                "amount24": 500_000_000.0, "funding_rate": 0.0001,
                "ts_ms": 1,
            },
            {
                "symbol": "ETH_USDT", "last_price": 3000.0,
                "bid1": 2999.5, "ask1": 3000.5,
                "hold_vol": 10_000_000.0,
                "amount24": 200_000_000.0, "funding_rate": 0.0002,
                "ts_ms": 2,
            },
        ]


def test_fetcher_update_keeps_existing_values():
    fetcher = BulkMetricsFetcher(
        rest=object(),  # DI; update icin gerekmiyor
        config=FetcherConfig(),
        contract_sizes={"BTC_USDT": 0.0001},
    )
    fetcher.update_contract_sizes({"BTC_USDT": 999.0, "ETH_USDT": 0.01})
    assert fetcher._contract_sizes["BTC_USDT"] == 0.0001  # DI kazandi
    assert fetcher._contract_sizes["ETH_USDT"] == 0.01


def test_universe_first_scan_triggers_bulk_fetch():
    rest = _FakeRest(bulk={"BTC_USDT": 0.0001, "ETH_USDT": 0.01})
    svc = UniverseService(
        rest=rest,
        fetcher_config=FetcherConfig(),
        contract_sizes={"BTC_USDT": 0.0001},
        always_include=("BTC_USDT",),
        excluded_symbols=frozenset(),
    )
    result = asyncio.run(svc.scan())
    assert rest.bulk_calls == 1
    assert "BTC_USDT" in result.top5
    # ETH bulk'tan geldi; ranklenebilir olmali
    assert "ETH_USDT" in result.top10


def test_universe_second_scan_no_refetch():
    rest = _FakeRest(bulk={"BTC_USDT": 0.0001, "ETH_USDT": 0.01})
    svc = UniverseService(
        rest=rest,
        fetcher_config=FetcherConfig(),
        contract_sizes={"BTC_USDT": 0.0001},
        always_include=("BTC_USDT",),
        excluded_symbols=frozenset(),
    )
    asyncio.run(svc.scan())
    asyncio.run(svc.scan())
    assert rest.bulk_calls == 1  # ikinci scan bulk fetch yapmaz


def test_universe_bulk_fetch_failure_does_not_break_scan():
    class _FailRest(_FakeRest):
        async def fetch_all_contract_details(self) -> dict[str, float]:
            self.bulk_calls += 1
            raise RuntimeError("network down")

    rest = _FailRest(bulk={})
    svc = UniverseService(
        rest=rest,
        fetcher_config=FetcherConfig(),
        contract_sizes={"BTC_USDT": 0.0001},
        always_include=("BTC_USDT",),
        excluded_symbols=frozenset(),
    )
    result = asyncio.run(svc.scan())
    assert result.top5 == ["BTC_USDT"]  # yalniz DI sembolu
    assert rest.bulk_calls == 1  # hata yutuldu, scan dondu