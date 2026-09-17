import pytest

from src.data_layer.metrics_fetcher import FetcherConfig
from src.data_layer.universe_service import UniverseService


class _FakeRest:
    def __init__(self, rows):
        self._rows = rows

    async def fetch_all_tickers(self):
        return self._rows


def _row(sym, price=100.0, hold=1_000_000_000.0,
         vol=200_000_000.0, funding=0.0001):
    return {
        "symbol": sym,
        "last_price": price,
        "bid1": price * 0.9995,
        "ask1": price * 1.0005,
        "hold_vol": hold,
        "amount24": vol,
        "funding_rate": funding,
        "ts_ms": 0,
    }


def _mk_service(rows, always=("BTC_USDT",)):
    rest = _FakeRest(rows)
    cs = {"BTC_USDT": 0.0001}
    for r in rows:
        cs[r["symbol"]] = 0.0001
    return UniverseService(rest, FetcherConfig(top_n=20), cs, always)


@pytest.mark.asyncio
async def test_scan_returns_top5():
    rows = [_row("SYM%d" % i, vol=200_000_000.0 - i * 1_000_000) for i in range(15)]
    svc = _mk_service(rows)
    result = await svc.scan()
    assert "BTC_USDT" in result.top5
    assert len(result.top5) <= 5
    assert len(result.top20) <= 20


@pytest.mark.asyncio
async def test_scan_empty_returns_always_include():
    svc = _mk_service([])
    result = await svc.scan()
    assert result.top5 == ["BTC_USDT"]


@pytest.mark.asyncio
async def test_always_include_at_top():
    rows = [_row("AAA", vol=500_000_000.0)]
    svc = _mk_service(rows, always=("BTC_USDT",))
    result = await svc.scan()
    assert result.top5[0] == "BTC_USDT"


@pytest.mark.asyncio
async def test_dedup_always_include():
    rows = [_row("BTC_USDT", vol=400_000_000.0)]
    svc = _mk_service(rows)
    result = await svc.scan()
    # BTC only once
    assert result.top5.count("BTC_USDT") == 1


@pytest.mark.asyncio
async def test_last_result_cached():
    svc = _mk_service([_row("A")])
    assert svc.last_result is None
    await svc.scan()
    assert svc.last_result is not None


def test_no_global_state():
    assert not hasattr(UniverseService, "_last_result")