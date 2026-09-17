_CS = {
    "GOOD": 0.0001, "LOW_OI": 0.0001, "HOT": 0.0001, "COLD": 0.0001,
    "TIGHT": 0.0001, "WIDE": 0.0001, "BIG": 0.0001, "SMALL": 0.0001,
    "JUNK1": 0.0001, "JUNK2": 0.0001,
}
for i in range(30):
    _CS["SYM%d" % i] = 0.0001

import pytest

from src.data_layer.metrics_fetcher import (
    BulkMetricsFetcher,
    FetcherConfig,
    RankedSymbol,
)


class _FakeRest:
    def __init__(self, rows):
        self._rows = rows

    async def fetch_all_tickers(self):
        return self._rows


def _row(sym, price=100.0, bid=99.9, ask=100.1, hold=1_000_000_000.0,
         vol=200_000_000.0, funding=0.0001):
    return {
        "symbol": sym,
        "last_price": price,
        "bid1": bid,
        "ask1": ask,
        "hold_vol": hold,
        "amount24": vol,
        "funding_rate": funding,
        "ts_ms": 0,
    }


def test_config_defaults():
    c = FetcherConfig()
    assert c.min_oi_usd == 1_000_000.0        # 5M -> 1M
    assert c.min_volume24_usd == 10_000_000.0 # 50M -> 10M
    assert c.min_spread_bps == 0.3            # 1.0 -> 0.3
    assert c.top_n == 20


@pytest.mark.asyncio
async def test_filters_low_oi():
    rest = _FakeRest([
        _row("GOOD", hold=1_000_000_000.0),  # 1B contracts × 0.0001 × 100 = 10M oi
        _row("LOW_OI", hold=1_000.0),        # 10k usd
    ])
    f = BulkMetricsFetcher(rest, FetcherConfig(), _CS)
    out = await f.fetch_and_rank()
    syms = [s.symbol for s in out]
    assert "GOOD" in syms
    assert "LOW_OI" not in syms


@pytest.mark.asyncio
async def test_filters_low_volume():
    rest = _FakeRest([
        _row("HOT", vol=200_000_000.0),
        _row("COLD", vol=5_000_000.0),  # 10M -> 5M (min_vol=10M)
    ])
    f = BulkMetricsFetcher(rest, FetcherConfig(), _CS)
    out = await f.fetch_and_rank()
    syms = [s.symbol for s in out]
    assert "HOT" in syms
    assert "COLD" not in syms


@pytest.mark.asyncio
async def test_filters_wide_spread():
    rest = _FakeRest([
        _row("TIGHT", bid=99.95, ask=100.05),  # ~10 bps
        _row("WIDE", bid=90.0, ask=110.0),     # huge
    ])
    f = BulkMetricsFetcher(rest, FetcherConfig(), _CS)
    out = await f.fetch_and_rank()
    syms = [s.symbol for s in out]
    assert "TIGHT" in syms
    assert "WIDE" not in syms


@pytest.mark.asyncio
async def test_scoring_volume_weight():
    rest = _FakeRest([
        _row("BIG", vol=1_000_000_000.0),
        _row("SMALL", vol=100_000_000.0),
    ])
    f = BulkMetricsFetcher(rest, FetcherConfig(), _CS)
    out = await f.fetch_and_rank()
    assert out[0].symbol == "BIG"


@pytest.mark.asyncio
async def test_top_n_limit():
    rows = [_row("SYM%d" % i, vol=200_000_000.0 + i) for i in range(30)]
    f = BulkMetricsFetcher(_FakeRest(rows), FetcherConfig(top_n=5), _CS)
    out = await f.fetch_and_rank()
    assert len(out) == 5


@pytest.mark.asyncio
async def test_empty_input():
    f = BulkMetricsFetcher(_FakeRest([]), FetcherConfig(), _CS)
    out = await f.fetch_and_rank()
    assert out == []


@pytest.mark.asyncio
async def test_all_filtered_returns_empty():
    rest = _FakeRest([
        _row("JUNK1", hold=100.0, vol=100.0),
        _row("JUNK2", hold=200.0, vol=200.0),
    ])
    f = BulkMetricsFetcher(rest, FetcherConfig(), _CS)
    out = await f.fetch_and_rank()
    assert out == []


def test_no_global_state():
    assert not hasattr(BulkMetricsFetcher, "_rest")