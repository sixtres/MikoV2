# tests/shadow/test_b3_3_runner_integration.py
"""B3.3 — ShadowRunner PaperPositionManager entegrasyon testleri.

Kapsam:
  - _setup_db: paper manager init + default PROD profili (F=C-PROD)
  - _apply_push -> paper.on_ws_tick (B3.3-B.3 freshness)
  - _on_ohlcv_1s -> paper.on_ohlcv (5s kova birleştirme)
  - _insert_ticker_snapshot -> paper.on_ticker (funding)
  - _micro_trigger_loop TRIGGER -> paper.on_entry
  - _micro_trigger_loop A.3: current_position_qty geri beslemesi

Mock: yok (in-process). tmp_path ile gecici sqlite.
Gercek ag yok. Kilitli kararlar: DURUM B3.3 A/B/C/D/E/F.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace

import pytest

from src.execution.paper_position_manager import _PaperPosition
from src.features.micro_trigger import MicroTriggerState
from src.backtest.signal_detector import Signal, SignalKind
from tests.shadow.runner import ShadowRunner


# ---------------------------------------------------------- helpers


def _runner(tmp_path) -> ShadowRunner:
    return ShadowRunner(
        symbols=["BTC_USDT"],
        duration_s=0,
        db_path=tmp_path / "test.sqlite",
        enable_rotation=False,
    )


def _warm_ohlcv(
    r: ShadowRunner, symbol: str = "BTC_USDT", n: int = 100,
    base: float = 100.0,
) -> None:
    """_on_ohlcv_1s uzerinden paper manager'i besle; ATR warmup."""
    for i in range(n):
        r._on_ohlcv_1s(symbol, {
            "sec": i + 1,
            "open": base, "high": base + 0.5,
            "low": base - 0.5, "close": base,
            "buy_vol": 1.0, "sell_vol": 1.0, "count": 1,
        })


# ---------------------------------------------------------- setup


def test_setup_db_creates_paper_manager(tmp_path) -> None:
    r = _runner(tmp_path)
    assert r._paper is None
    r._setup_db()
    assert r._paper is not None


def test_setup_db_default_profile_is_prod(tmp_path) -> None:
    """SORU B3.3-F = (C-PROD): default PROD 0.006/2."""
    r = _runner(tmp_path)
    r._setup_db()
    assert r._paper._cfg.config_profile_tag == "PAPER_PROD"
    assert r._paper._cfg.risk_pct == pytest.approx(0.006)
    assert r._paper._cfg.max_positions_global == 2
    assert r._paper._cfg.max_positions_per_symbol == 1


# ---------------------------------------------------------- feed entegrasyonu


def test_apply_push_feeds_paper_last_price(tmp_path) -> None:
    """B3.3-B.3: WS tick -> paper last_price (mid) beslemesi."""
    r = _runner(tmp_path)
    r._setup_db()
    r._apply_snapshot("BTC_USDT", {
        "bids": [(100.0, 1.0)],
        "asks": [(100.2, 1.0)],
        "version": 1, "ts": 0,
    })
    r._apply_push("BTC_USDT", {
        "bids": [[100.0, 1.0]],
        "asks": [[100.2, 1.0]],
    })
    assert r._paper._last_price["BTC_USDT"] == pytest.approx(100.1)


def test_on_ohlcv_1s_feeds_paper_manager(tmp_path) -> None:
    """paper manager 1s event'leri 5s kovaya birleştirir."""
    r = _runner(tmp_path)
    r._setup_db()
    _warm_ohlcv(r, "BTC_USDT", 100)
    dq = r._paper._candles.get("BTC_USDT")
    assert dq is not None
    # 100 1s sec -> 20 adet 5s kova (son kova kapanmamis olabilir)
    assert len(dq) >= 18


def test_insert_ticker_snapshot_feeds_paper_funding(tmp_path) -> None:
    """Funding rate -> paper.on_ticker."""
    r = _runner(tmp_path)
    r._setup_db()
    ticker = {
        "symbol": "BTC_USDT",
        "ts_ms": 1_000_000,
        "last_price": 100.0,
        "fair_price": 100.0,
        "index_price": 100.0,
        "hold_vol": 10.0,
    }
    funding = {"funding_rate": 0.0005, "next_settle_ms": 2_000_000}
    r._insert_ticker_snapshot(ticker, funding, oi_usdt=0.0)
    assert r._paper._last_funding_rate["BTC_USDT"] == pytest.approx(0.0005)


# ---------------------------------------------------------- micro_trigger_loop


@pytest.mark.asyncio
async def test_micro_trigger_loop_triggers_paper_entry(tmp_path) -> None:
    """TRIGGER gecisi -> paper.on_entry cagrilir."""
    r = _runner(tmp_path)
    r._setup_db()
    r._mt_config = replace(r._mt_config, timer_sleep_ms=10)

    _warm_ohlcv(r, "BTC_USDT", 100)
    r._paper.on_ws_tick("BTC_USDT", 100.0)
    r._last_price["BTC_USDT"] = 100.0
    r._last_ws_data_mono["BTC_USDT"] = time.monotonic()

    # LONG setup sinyalleri (SWEEP_DOWN + MSS_UP + FVG_BULLISH)
    r._recent_signals["BTC_USDT"].append(
        (1000, Signal(SignalKind.SWEEP_DOWN, 1000, 100.0))
    )
    r._recent_signals["BTC_USDT"].append(
        (1000, Signal(SignalKind.MSS_UP, 1000, 100.0))
    )
    r._recent_signals["BTC_USDT"].append(
        (1000, Signal(SignalKind.FVG_BULLISH, 1000, 100.0))
    )

    async def fake_evaluate(*args, **kw):
        return MicroTriggerState.TRIGGER

    r._micro_triggers["BTC_USDT"].evaluate = fake_evaluate

    task = asyncio.create_task(r._micro_trigger_loop())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert "BTC_USDT" in r._paper.open_positions


@pytest.mark.asyncio
async def test_micro_trigger_loop_feeds_current_position_qty(tmp_path) -> None:
    """SORU B3.3-A.3: evaluate cagrisi acik pozisyon qty'sini alir."""
    r = _runner(tmp_path)
    r._setup_db()
    r._mt_config = replace(r._mt_config, timer_sleep_ms=10)

    # elle pozisyon enjekte et
    r._paper._positions["BTC_USDT"] = _PaperPosition(
        position_id="test-1",
        symbol="BTC_USDT",
        direction="LONG",
        entry_ts_ms=1000,
        entry_bucket_sec=0,
        entry_price=100.0,
        qty=1.5,
        sl_price=99.0,
        tp_price=102.0,
        entry_fee=0.02,
    )
    r._last_ws_data_mono["BTC_USDT"] = time.monotonic()

    captured: list[dict] = []

    async def fake_evaluate(symbol, **kw):
        captured.append(kw)
        return MicroTriggerState.IDLE

    r._micro_triggers["BTC_USDT"].evaluate = fake_evaluate

    task = asyncio.create_task(r._micro_trigger_loop())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert captured, "evaluate hic cagrilmadi"
    assert captured[-1]["current_position_qty"] == pytest.approx(1.5)