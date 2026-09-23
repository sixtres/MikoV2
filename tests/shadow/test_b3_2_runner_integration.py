# tests/shadow/test_b3_2_runner_integration.py
"""B3.2 — ShadowRunner entegrasyon testleri.

Kapsam:
  - _on_ohlcv_1s -> detector + shadow strategy beslemesi
  - _on_ohlcv_1s -> last_price / last_exchange_ts guncellemesi
  - _log_entry_signal JSON alan butunlugu
  - _emit_micro_event cagri yolu
  - _apply_rotation -> _init_symbol_state tetiklenmesi
  - TRIGGER transition -> EntrySignal log + state reset

Telemetry entegrasyonu B3.3'e ertelendi (DURUM §11 SORU SS=C).
Kilitli kararlar: DURUM §11 SORU B3.2-A/B/C/D/E.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.backtest.signal_detector import Signal, SignalKind
from src.backtest.strategy import Direction, EntrySignal
from src.data_layer.universe_service import RotationDecision
from src.features.micro_trigger import MicroTriggerState
from tests.shadow.runner import ShadowRunner


T0 = 1_700_000_000_000


def _runner(symbols=("BTC_USDT",)) -> ShadowRunner:
    return ShadowRunner(
        symbols=list(symbols),
        duration_s=0,
        db_path=None,
        enable_rotation=False,
    )


def _bucket(sec: int = 1, price: float = 100.0) -> dict:
    return {
        "sec": sec,
        "open": price,
        "high": price + 0.5,
        "low": price - 0.5,
        "close": price,
        "buy_vol": 10.0,
        "sell_vol": 5.0,
        "count": 3,
    }


def _json_records(caplog) -> list:
    out = []
    for rec in caplog.records:
        msg = rec.getMessage()
        if isinstance(msg, str) and msg.startswith("{"):
            try:
                out.append(json.loads(msg))
            except json.JSONDecodeError:
                continue
    return out


# ---------------------------------------------------------- _on_ohlcv_1s

def test_on_ohlcv_1s_feeds_detector_to_recent_signals() -> None:
    r = _runner()
    sym = "BTC_USDT"
    sig = Signal(kind=SignalKind.SWEEP_DOWN, ts_ms=T0, price=100.0)

    def fake_feed(ev):
        return [sig]

    r._mt_detectors[sym].feed_ohlcv_1s = fake_feed
    r._on_ohlcv_1s(sym, _bucket(sec=1))

    assert len(r._recent_signals[sym]) == 1
    assert r._recent_signals[sym][-1] == (T0, sig)


def test_on_ohlcv_1s_feeds_shadow_strategy_and_logs(caplog) -> None:
    r = _runner()
    sym = "BTC_USDT"
    entry = EntrySignal(
        direction=Direction.LONG,
        ts_ms=T0,
        price=100.0,
        reason="test_setup",
        signals=(),
    )

    def fake_on_ohlcv(ev):
        return [entry]

    r._shadow_strategies[sym].on_ohlcv = fake_on_ohlcv
    caplog.set_level(logging.INFO, logger="shadow")

    r._on_ohlcv_1s(sym, _bucket(sec=1))

    matches = [
        e for e in _json_records(caplog)
        if e.get("event") == "ENTRY_SIGNAL" and e.get("source") == "STRATEGY"
    ]
    assert len(matches) == 1
    assert matches[0]["direction"] == "LONG"
    assert matches[0]["symbol"] == sym
    assert matches[0]["reason"] == "test_setup"


def test_on_ohlcv_1s_updates_last_price_and_exchange_ts() -> None:
    r = _runner()
    sym = "BTC_USDT"
    r._on_ohlcv_1s(sym, _bucket(sec=42, price=105.5))

    assert r._last_price[sym] == 105.5
    assert r._last_exchange_ts[sym] == 42 * 1000


# ---------------------------------------------------------- log format

def test_log_entry_signal_json_fields(caplog) -> None:
    r = _runner()
    caplog.set_level(logging.INFO, logger="shadow")

    r._log_entry_signal(
        source="MICRO_TRIGGER",
        symbol="BTC_USDT",
        direction=Direction.LONG,
        price=100.0,
        ts_ms=T0,
        reason="test",
    )

    recs = _json_records(caplog)
    assert len(recs) == 1
    p = recs[0]
    assert p["event"] == "ENTRY_SIGNAL"
    assert p["source"] == "MICRO_TRIGGER"
    assert p["symbol"] == "BTC_USDT"
    assert p["direction"] == "LONG"
    assert p["price"] == 100.0
    assert p["ts_ms"] == T0
    assert p["reason"] == "test"


def test_emit_micro_event_logs(caplog) -> None:
    r = _runner()
    caplog.set_level(logging.INFO, logger="shadow")

    r._emit_micro_event("SWEEP", {"symbol": "BTC_USDT", "reason": "test"})

    recs = _json_records(caplog)
    assert len(recs) == 1
    p = recs[0]
    assert p["event"] == "SWEEP"
    assert p["source"] == "MICRO_TRIGGER"
    assert p["symbol"] == "BTC_USDT"
    assert p["reason"] == "test"


# ---------------------------------------------------------- rotation -> init

@pytest.mark.asyncio
async def test_apply_rotation_inits_symbol_state() -> None:
    r = _runner(symbols=("BTC_USDT",))
    r.ws = MagicMock()
    r.ws.subscribe = AsyncMock(return_value=True)
    r.ws.unsubscribe = AsyncMock(return_value=True)
    r.rest = MagicMock()
    r.rest.fetch_snapshot = AsyncMock(
        return_value={
            "version": 1,
            "bids": [[100.0, 1.0]],
            "asks": [[100.1, 1.0]],
        }
    )
    r.rest.fetch_contract_size = AsyncMock(return_value=0.0001)
    r.seq_validator.set_epoch = AsyncMock(return_value=None)
    r.seq_validator.set_last_u = AsyncMock(return_value=None)

    decision = RotationDecision(
        to_subscribe=("SOL_USDT",),
        to_unsubscribe=(),
        watch_symbols=(),
        quarantined=(),
        scan_ms=T0,
        subscribed_after=("BTC_USDT", "SOL_USDT"),
    )
    await r._apply_rotation(decision)

    assert "SOL_USDT" in r._micro_triggers
    assert "SOL_USDT" in r._mt_detectors
    assert "SOL_USDT" in r._shadow_strategies
    assert "SOL_USDT" in r._shadow_detectors
    assert "SOL_USDT" in r._recent_signals


# ---------------------------------------------------------- TRIGGER flow

@pytest.mark.asyncio
async def test_micro_trigger_trigger_flow_logs_and_resets(caplog) -> None:
    r = _runner()
    sym = "BTC_USDT"
    r._mt_config = replace(r._mt_config, timer_sleep_ms=10)

    r._recent_signals[sym].append(
        (T0, Signal(SignalKind.SWEEP_DOWN, T0, 100.0))
    )
    r._recent_signals[sym].append(
        (T0, Signal(SignalKind.MSS_UP, T0, 100.0))
    )
    r._recent_signals[sym].append(
        (T0, Signal(SignalKind.FVG_BULLISH, T0, 100.0))
    )
    r._last_price[sym] = 100.0

    async def fake_eval(*a, **kw):
        return MicroTriggerState.TRIGGER

    r._micro_triggers[sym].evaluate = fake_eval
    r._last_mt_state[sym] = MicroTriggerState.FVG_OTE

    caplog.set_level(logging.INFO, logger="shadow")

    task = asyncio.create_task(r._micro_trigger_loop())
    await asyncio.sleep(0.08)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    matches = [
        e for e in _json_records(caplog)
        if e.get("event") == "ENTRY_SIGNAL" and e.get("source") == "MICRO_TRIGGER"
    ]
    assert len(matches) >= 1
    assert matches[0]["direction"] == "LONG"
    assert matches[0]["symbol"] == sym
    assert r._last_mt_state[sym] == MicroTriggerState.IDLE