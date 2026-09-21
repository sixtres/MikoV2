# B2e.-1: §6.1 funding ceza + §6.2 emtia exclude compliance testleri
# SORU A': B2e.-1 ayri test dosyasi

import pytest

from src.data_layer.constants import (
    EXCLUDED_SYMBOLS,
    EXCLUDED_SYMBOLS_VERSION,
)
from src.data_layer.metrics_fetcher import BulkMetricsFetcher, FetcherConfig
from src.data_layer.universe_service import ScanResult, UniverseService


class _FakeRest:
    def __init__(self, rows):
        self._rows = rows

    async def fetch_all_tickers(self):
        return self._rows


def _row(sym, price=100.0, bid=99.9, ask=100.1,
         hold=1_000_000_000.0, vol=200_000_000.0, funding=0.0001):
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


def _cs(*symbols):
    return {s: 0.0001 for s in symbols}


# ---------- §6.2 constants ----------

def test_excluded_symbols_canonical_list():
    expected = {
        "XAUT_USDT", "XAU_USDT", "XAG_USDT",
        "SILVER_USDT", "GOLD_USDT",
        "UKOIL_USDT", "USOIL_USDT",
        "SPCXSTOCK_USDT",
    }
    assert expected == set(EXCLUDED_SYMBOLS)
    assert isinstance(EXCLUDED_SYMBOLS, frozenset)


def test_excluded_symbols_version_positive():
    assert isinstance(EXCLUDED_SYMBOLS_VERSION, int)
    assert EXCLUDED_SYMBOLS_VERSION >= 1


def test_excluded_symbols_is_frozen():
    with pytest.raises(AttributeError):
        EXCLUDED_SYMBOLS.add("NEW_USDT")  # type: ignore[attr-defined]


# ---------- §6.2 exclude filtresi ----------

@pytest.mark.asyncio
async def test_excluded_symbol_filtered_from_ranking():
    cs = _cs("XAUT_USDT", "BTC_USDT")
    rest = _FakeRest([
        _row("XAUT_USDT", vol=1_000_000_000.0),
        _row("BTC_USDT", vol=100_000_000.0),
    ])
    f = BulkMetricsFetcher(
        rest, FetcherConfig(), cs,
        excluded_symbols=EXCLUDED_SYMBOLS,
    )
    out = await f.fetch_and_rank()
    syms = [s.symbol for s in out]
    assert "XAUT_USDT" not in syms
    assert "BTC_USDT" in syms


@pytest.mark.asyncio
async def test_exclude_applied_before_normalization():
    # XAUT devasa volume: filtreden once ele alinmazsa max_vol sisirilir
    cs = _cs("XAUT_USDT", "A", "B")
    rest = _FakeRest([
        _row("XAUT_USDT", vol=10_000_000_000.0),
        _row("A", vol=100_000_000.0),
        _row("B", vol=50_000_000.0),
    ])
    f = BulkMetricsFetcher(
        rest,
        FetcherConfig(weight_volume=1.0, weight_oi=0.0, weight_funding=0.0),
        cs,
        excluded_symbols=EXCLUDED_SYMBOLS,
    )
    out = await f.fetch_and_rank()
    a = next(s for s in out if s.symbol == "A")
    # A, normalize edilmis tepe olmali (max_vol = A'nin volume'u)
    assert abs(a.score - 1.0) < 1e-9


@pytest.mark.asyncio
async def test_exclude_empty_keeps_all():
    cs = _cs("XAUT_USDT")
    rest = _FakeRest([_row("XAUT_USDT")])
    f = BulkMetricsFetcher(rest, FetcherConfig(), cs)
    out = await f.fetch_and_rank()
    assert out[0].symbol == "XAUT_USDT"


@pytest.mark.asyncio
async def test_exclude_multiple_emtia_symbols():
    symbols = ["XAUT_USDT", "SILVER_USDT", "UKOIL_USDT", "GOLD_USDT", "BTC_USDT"]
    cs = _cs(*symbols)
    rest = _FakeRest([_row(s) for s in symbols])
    f = BulkMetricsFetcher(
        rest, FetcherConfig(), cs,
        excluded_symbols=EXCLUDED_SYMBOLS,
    )
    out = await f.fetch_and_rank()
    assert {s.symbol for s in out} == {"BTC_USDT"}


# ---------- §6.1 funding ceza ----------

@pytest.mark.asyncio
async def test_funding_penalty_above_threshold():
    cs = _cs("EXTREME", "NORMAL")
    rest = _FakeRest([
        _row("EXTREME", funding=0.02, vol=200_000_000.0),
        _row("NORMAL", funding=0.001, vol=200_000_000.0),
    ])
    f = BulkMetricsFetcher(
        rest,
        FetcherConfig(weight_volume=0.0, weight_oi=0.0, weight_funding=1.0),
        cs,
    )
    out = await f.fetch_and_rank()
    by = {s.symbol: s for s in out}
    assert abs(by["NORMAL"].score - 0.2) < 1e-9
    assert abs(by["EXTREME"].score - (-1.0)) < 1e-9
    assert out[0].symbol == "NORMAL"


@pytest.mark.asyncio
async def test_funding_penalty_negative_sign():
    # negatif asiri funding (short squeeze) da ceza almali (abs)
    cs = _cs("NEG_EXTREME", "NEG_MILD")
    rest = _FakeRest([
        _row("NEG_EXTREME", funding=-0.02, vol=200_000_000.0),
        _row("NEG_MILD", funding=-0.001, vol=200_000_000.0),
    ])
    f = BulkMetricsFetcher(
        rest,
        FetcherConfig(weight_volume=0.0, weight_oi=0.0, weight_funding=1.0),
        cs,
    )
    out = await f.fetch_and_rank()
    by = {s.symbol: s for s in out}
    assert abs(by["NEG_MILD"].score - 0.2) < 1e-9
    assert abs(by["NEG_EXTREME"].score - (-1.0)) < 1e-9
    assert out[0].symbol == "NEG_MILD"


@pytest.mark.asyncio
async def test_funding_boundary_at_threshold():
    # tam 0.005 esik: ceza YOK (esik strict > 0.005)
    cs = _cs("AT", "ABOVE")
    rest = _FakeRest([
        _row("AT", funding=0.005, vol=200_000_000.0),
        _row("ABOVE", funding=0.005001, vol=200_000_000.0),
    ])
    f = BulkMetricsFetcher(
        rest,
        FetcherConfig(weight_volume=0.0, weight_oi=0.0, weight_funding=1.0),
        cs,
    )
    out = await f.fetch_and_rank()
    by = {s.symbol: s for s in out}
    assert abs(by["AT"].score - 1.0) < 1e-9
    assert abs(by["ABOVE"].score - (-1.0)) < 1e-9


@pytest.mark.asyncio
async def test_funding_linear_below_threshold():
    cs = _cs("LOW", "HIGH")
    rest = _FakeRest([
        _row("LOW", funding=0.001, vol=200_000_000.0),
        _row("HIGH", funding=0.004, vol=200_000_000.0),
    ])
    f = BulkMetricsFetcher(
        rest,
        FetcherConfig(weight_volume=0.0, weight_oi=0.0, weight_funding=1.0),
        cs,
    )
    out = await f.fetch_and_rank()
    by = {s.symbol: s for s in out}
    assert abs(by["LOW"].score - 0.2) < 1e-9
    assert abs(by["HIGH"].score - 0.8) < 1e-9


# ---------- UniverseService entegrasyon ----------

@pytest.mark.asyncio
async def test_universe_service_records_excluded_symbols():
    cs = _cs("BTC_USDT", "XAUT_USDT")
    rest = _FakeRest([
        _row("BTC_USDT"),
        _row("XAUT_USDT", vol=1_000_000_000.0),
    ])
    svc = UniverseService(rest, FetcherConfig(), cs)
    result = await svc.scan()
    assert isinstance(result, ScanResult)
    assert "XAUT_USDT" not in result.top5
    assert "XAUT_USDT" not in result.top20
    assert "XAUT_USDT" in result.excluded_symbols
    assert "BTC_USDT" not in result.excluded_symbols


@pytest.mark.asyncio
async def test_universe_service_excluded_in_always_include_dropped(caplog):
    cs = _cs("XAUT_USDT")
    rest = _FakeRest([_row("XAUT_USDT")])
    svc = UniverseService(
        rest, FetcherConfig(), cs,
        always_include=("XAUT_USDT",),
    )
    result = await svc.scan()
    assert "XAUT_USDT" not in result.top5


@pytest.mark.asyncio
async def test_universe_service_custom_exclude_set():
    cs = _cs("A", "B")
    rest = _FakeRest([_row("A"), _row("B")])
    svc = UniverseService(
        rest, FetcherConfig(), cs,
        always_include=(),
        excluded_symbols=frozenset({"A"}),
    )
    result = await svc.scan()
    assert "A" not in result.top5
    assert "B" in result.top5
    assert result.excluded_symbols == ["A"]


@pytest.mark.asyncio
async def test_universe_service_default_btc_unaffected():
    # default EXCLUDED_SYMBOLS BTC_USDT icermez; always_include saglam
    cs = _cs("BTC_USDT")
    rest = _FakeRest([_row("BTC_USDT")])
    svc = UniverseService(rest, FetcherConfig(), cs)
    result = await svc.scan()
    assert result.top5[0] == "BTC_USDT"