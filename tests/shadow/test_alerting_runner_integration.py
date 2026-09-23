"""B3.4 Mod 2 — ShadowRunner ↔ AlertAgent entegrasyon testleri (T7)."""
from __future__ import annotations

import asyncio
import dataclasses as _dc
import os
import time

import pytest

from src.backtest.signal_detector import SignalKind
from src.features.micro_trigger import MicroTriggerState
from tests.shadow.runner import ShadowRunner


class FakeAgent:
    def __init__(self) -> None:
        self.emits: list = []
        self.stops: int = 0

    async def emit(self, event_type, payload):
        self.emits.append((event_type, payload))
        return 1

    async def stop(self) -> None:
        self.stops += 1


class FakeSignal:
    def __init__(self, kind, ts_ms: int) -> None:
        self.kind = kind
        self.ts_ms = ts_ms


def _clear_alert_env(monkeypatch) -> None:
    for k in list(os.environ.keys()):
        if k.startswith("MIKOV2_ALERT_"):
            monkeypatch.delenv(k, raising=False)


def test_runner_alert_disabled_when_no_env(tmp_path, monkeypatch):
    _clear_alert_env(monkeypatch)
    runner = ShadowRunner(
        ["BTC_USDT"], duration_s=1, db_path=tmp_path / "t.db"
    )
    runner._setup_db()
    try:
        assert runner._alert_config is None
        assert runner._alert_agent is None
    finally:
        if runner._conn is not None:
            runner._conn.close()


def test_runner_alert_config_loaded_from_env(tmp_path, monkeypatch):
    _clear_alert_env(monkeypatch)
    monkeypatch.setenv("MIKOV2_ALERT_TELEGRAM_TOKEN", "T")
    monkeypatch.setenv("MIKOV2_ALERT_TELEGRAM_CHAT_ID", "C")
    runner = ShadowRunner(
        ["BTC_USDT"], duration_s=1, db_path=tmp_path / "t.db"
    )
    runner._setup_db()
    try:
        assert runner._alert_config is not None
        assert runner._alert_config.telegram_enabled is True
    finally:
        if runner._conn is not None:
            runner._conn.close()


def test_runner_alert_config_invalid_disables(tmp_path, monkeypatch):
    _clear_alert_env(monkeypatch)
    # token var, chat_id yok → AlertConfig.validate ValueError
    monkeypatch.setenv("MIKOV2_ALERT_TELEGRAM_TOKEN", "T")
    runner = ShadowRunner(
        ["BTC_USDT"], duration_s=1, db_path=tmp_path / "t.db"
    )
    runner._setup_db()
    try:
        assert runner._alert_config is None
    finally:
        if runner._conn is not None:
            runner._conn.close()


def test_emit_micro_event_no_agent_no_raise():
    runner = ShadowRunner(["BTC_USDT"], duration_s=1, db_path=None)
    runner._alert_agent = None
    # Running loop yoksa da hata yok
    runner._emit_micro_event("TRIGGER", {"symbol": "BTC_USDT"})


def test_emit_micro_event_forwards_to_agent():
    runner = ShadowRunner(["BTC_USDT"], duration_s=1, db_path=None)
    fake = FakeAgent()
    runner._alert_agent = fake

    async def _go():
        runner._emit_micro_event(
            "TRIGGER", {"symbol": "BTC_USDT", "reason": "x"}
        )
        await asyncio.sleep(0.01)

    asyncio.run(_go())
    assert len(fake.emits) == 1
    et, pl = fake.emits[0]
    assert et == "TRIGGER"
    assert pl["symbol"] == "BTC_USDT"
    assert pl["source"] == "MICRO_TRIGGER"


def test_micro_trigger_loop_emits_entry_on_trigger():
    runner = ShadowRunner(["BTC_USDT"], duration_s=1, db_path=None)
    fake = FakeAgent()
    runner._alert_agent = fake
    try:
        runner._mt_config = _dc.replace(
            runner._mt_config, timer_sleep_ms=50
        )
    except Exception:
        pass

    async def _go():
        async def fake_evaluate(*a, **kw):
            return MicroTriggerState.TRIGGER

        runner._micro_triggers["BTC_USDT"].evaluate = fake_evaluate
        now_ms = int(time.time() * 1000)
        dq = runner._recent_signals["BTC_USDT"]
        dq.append((now_ms, FakeSignal(SignalKind.SWEEP_DOWN, now_ms)))
        dq.append((now_ms, FakeSignal(SignalKind.MSS_UP, now_ms)))
        dq.append((now_ms, FakeSignal(SignalKind.FVG_BULLISH, now_ms)))
        runner._last_ws_data_mono["BTC_USDT"] = time.monotonic()
        runner._last_price["BTC_USDT"] = 100.0

        task = asyncio.create_task(runner._micro_trigger_loop())
        for _ in range(20):
            await asyncio.sleep(0.02)
            if any(et == "ENTRY" for et, _ in fake.emits):
                break
        runner._shutdown_event.set()
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()
            try:
                await task
            except Exception:
                pass

    asyncio.run(_go())
    assert any(et == "ENTRY" for et, _ in fake.emits), fake.emits


def test_micro_trigger_loop_skips_quarantined():
    runner = ShadowRunner(["BTC_USDT"], duration_s=1, db_path=None)
    fake = FakeAgent()
    runner._alert_agent = fake
    try:
        runner._mt_config = _dc.replace(
            runner._mt_config, timer_sleep_ms=50
        )
    except Exception:
        pass

    async def _go():
        evaluate_calls: list = []
        quarantine_checks: list = []

        async def fake_evaluate(*a, **kw):
            evaluate_calls.append(1)
            return MicroTriggerState.TRIGGER

        mt = runner._micro_triggers["BTC_USDT"]
        mt.evaluate = fake_evaluate
        real_is_quarantined = mt.is_quarantined

        def spy_is_quarantined(symbol):
            quarantine_checks.append(symbol)
            return real_is_quarantined(symbol)

        mt.is_quarantined = spy_is_quarantined
        mt.quarantine("BTC_USDT", "test")

        # quarantine() MICRO_TRIGGER_QUARANTINE event'ini fire-and-forget
        # task ile alert agent'a yollar. clear() öncesi task'ın
        # execute olmasını bekle.
        await asyncio.sleep(0.05)
        fake.emits.clear()
        runner._last_ws_data_mono["BTC_USDT"] = time.monotonic()

        task = asyncio.create_task(runner._micro_trigger_loop())
        await asyncio.sleep(0.3)
        runner._shutdown_event.set()
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()
            try:
                await task
            except Exception:
                pass

        # False-positive önleme: loop gerçekten tick atmadıysa skip
        # iddiası doğrulanamaz; quarantine_checks boş kalır → fail.
        assert len(quarantine_checks) >= 1, (
            "loop tick atmadı; skip iddiası doğrulanamaz"
        )
        assert evaluate_calls == [], evaluate_calls
        assert fake.emits == [], fake.emits

    asyncio.run(_go())