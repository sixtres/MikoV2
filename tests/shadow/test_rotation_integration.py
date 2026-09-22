# tests/shadow/test_rotation_integration.py
"""B3.1 rotation integration tests.

ShadowRunner + UniverseService etkileşimi:
  - apply_rotation: WS subscribe/unsubscribe çağrıları
  - watch_symbols runner tarafında saklanır
  - tickers poll Top5 ∪ watch sembolleri çeker
  - per-symbol watchdog iptal edilebilir
  - Top5→Top4 daralma uyarısı (SORU F=C)
  - aggregate rapor alanları

Mock: MEXCWSClient ve MEXCRestClient — gerçek ağ yok.
Kilitli kararlar: DURUM §11 B3.1 A–G, Q1–Q5 (dış-ajan sentezi).
"""

from __future__ import annotations

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data_layer.universe_service import RotationDecision
from tests.shadow.runner import ShadowRunner


T0 = 1_700_000_000_000


def _mock_rest() -> MagicMock:
    rest = MagicMock()
    rest.fetch_contract_size = AsyncMock(return_value=0.0001)
    rest.fetch_snapshot = AsyncMock(return_value={
        "version": 100,
        "bids": [[100.0, 1.0]],
        "asks": [[100.1, 1.0]],
    })
    rest.fetch_ticker = AsyncMock(return_value={
        "ts_ms": T0,
        "symbol": "BTC_USDT",
        "last_price": 100.0,
        "fair_price": 100.0,
        "index_price": 100.0,
        "hold_vol": 1000.0,
    })
    rest.fetch_funding_rate = AsyncMock(return_value={
        "funding_rate": 0.0001,
        "next_settle_ms": T0 + 8 * 3600 * 1000,
    })
    return rest


def _mock_ws() -> MagicMock:
    ws = MagicMock()
    ws.connect = AsyncMock(return_value=None)
    ws.close = AsyncMock(return_value=None)
    ws.subscribe = AsyncMock(return_value=True)
    ws.unsubscribe = AsyncMock(return_value=True)
    ws._last_data_mono = 0.0
    return ws


def _runner(symbols=("BTC_USDT", "ETH_USDT")) -> ShadowRunner:
    return ShadowRunner(
        symbols=list(symbols),
        duration_s=0,
        db_path=None,
        enable_rotation=False,
    )


def _decision(
    to_sub=(),
    to_unsub=(),
    watch=(),
    after=(),
) -> RotationDecision:
    return RotationDecision(
        to_subscribe=tuple(to_sub),
        to_unsubscribe=tuple(to_unsub),
        watch_symbols=tuple(watch),
        quarantined=(),
        scan_ms=T0,
        subscribed_after=tuple(after),
    )


@pytest.mark.asyncio
async def test_apply_rotation_subscribes_new_symbols():
    runner = _runner()
    runner.ws = _mock_ws()
    runner.rest = _mock_rest()
    await runner._apply_rotation(
        _decision(to_sub=("SOL_USDT",),
                  after=("BTC_USDT", "ETH_USDT", "SOL_USDT"))
    )
    runner.ws.subscribe.assert_awaited_once_with("SOL_USDT")
    assert "SOL_USDT" in runner.symbols
    assert runner.synced.get("SOL_USDT") is True
    assert runner.last_applied_version.get("SOL_USDT") == 100


@pytest.mark.asyncio
async def test_apply_rotation_unsubscribes():
    runner = _runner()
    runner.ws = _mock_ws()
    runner.rest = _mock_rest()
    await runner._apply_rotation(
        _decision(to_unsub=("ETH_USDT",), after=("BTC_USDT",))
    )
    runner.ws.unsubscribe.assert_awaited_once_with("ETH_USDT")
    assert "ETH_USDT" not in runner.symbols


@pytest.mark.asyncio
async def test_apply_rotation_sets_watch_symbols():
    runner = _runner()
    runner.ws = _mock_ws()
    runner.rest = _mock_rest()
    await runner._apply_rotation(
        _decision(watch=("SOL_USDT", "XRP_USDT"),
                  after=("BTC_USDT", "ETH_USDT"))
    )
    assert runner._watch_symbols == {"SOL_USDT", "XRP_USDT"}


@pytest.mark.asyncio
async def test_tickers_poll_covers_watch_symbols():
    runner = _runner()
    runner.rest = _mock_rest()
    runner._contract_size = {"BTC_USDT": 0.0001, "ETH_USDT": 0.0001}
    runner._watch_symbols = {"XRP_USDT"}

    async def _stop_soon():
        await asyncio.sleep(0.05)
        runner._shutdown_event.set()

    stopper = asyncio.create_task(_stop_soon())
    await runner._tickers_poll_task()
    await stopper

    called = {c.args[0] for c in runner.rest.fetch_ticker.await_args_list}
    assert "BTC_USDT" in called
    assert "ETH_USDT" in called
    assert "XRP_USDT" in called


@pytest.mark.asyncio
async def test_per_symbol_watchdog_cancellable():
    runner = _runner()
    runner.ws = _mock_ws()
    runner._last_ws_data_mono = {"BTC_USDT": time.monotonic()}
    task = asyncio.create_task(runner._per_symbol_watchdog())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert task.cancelled()


def test_check_top5_daralma_warns(caplog):
    runner = _runner(symbols=("BTC_USDT",))
    caplog.set_level(logging.WARNING, logger="shadow")
    runner._check_top5_daralma()
    assert any(
        "TOP5_DARALMA_ALERT" in r.getMessage()
        for r in caplog.records
    )


def test_aggregate_report_shape():
    runner = _runner()
    runner.symbols = {"BTC_USDT", "ETH_USDT"}
    runner._watch_symbols = {"XRP_USDT"}
    report = runner._aggregate_report()
    assert set(report["ws_symbols"]) == {"BTC_USDT", "ETH_USDT"}
    assert set(report["watch_symbols"]) == {"XRP_USDT"}
    assert "quarantined" in report