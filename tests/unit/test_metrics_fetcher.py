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
    assert c.min_oi_usd == 5_000_000.0
    assert c.min_volume24_usd == 50_000_000.0
    assert c.top_n == 20


@pytest.mark.asyncio
async def test_filters_low_oi():
    rest = _FakeRest([
        _row("GOOD", hold=1_000_000_000.0),  # 1B contracts × 0.0001 × 100 = 10M oi
        _row("LOW_OI", hold=1_000.0),        # 10k usd
    ])
    f = BulkMetricsFetcher(rest, FetcherConfig())
    out = await f.fetch_and_rank()
    syms = [s.symbol for s in out]
    assert "GOOD" in syms
    assert "LOW_OI" not in syms


@pytest.mark.asyncio
async def test_filters_low_volume():
    rest = _FakeRest([
        _row("HOT", vol=200_000_000.0),
        _row("COLD", vol=10_000_000.0),
    ])
    f = BulkMetricsFetcher(rest, FetcherConfig())
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
    f = BulkMetricsFetcher(rest, FetcherConfig())
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
    f = BulkMetricsFetcher(rest, FetcherConfig())
    out = await f.fetch_and_rank()
    assert out[0].symbol == "BIG"


@pytest.mark.asyncio
async def test_top_n_limit():
    rows = [_row("SYM%d" % i, vol=200_000_000.0 + i) for i in range(30)]
    f = BulkMetricsFetcher(_FakeRest(rows), FetcherConfig(top_n=5))
    out = await f.fetch_and_rank()
    assert len(out) == 5


@pytest.mark.asyncio
async def test_empty_input():
    f = BulkMetricsFetcher(_FakeRest([]), FetcherConfig())
    out = await f.fetch_and_rank()
    assert out == []


@pytest.mark.asyncio
async def test_all_filtered_returns_empty():
    rest = _FakeRest([
        _row("JUNK1", hold=100.0, vol=100.0),
        _row("JUNK2", hold=200.0, vol=200.0),
    ])
    f = BulkMetricsFetcher(rest, FetcherConfig())
    out = await f.fetch_and_rank()
    assert out == []


def test_no_global_state():
    assert not hasattr(BulkMetricsFetcher, "_rest")