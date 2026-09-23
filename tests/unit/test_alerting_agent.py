# tests/unit/test_alerting_agent.py
"""B3.4 Mod 2 — AlertAgent testleri (T4)."""
from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest

from src.alerting.agent import (
    AlertAgent,
    AlertConfig,
    config_from_env,
    _BREAKER_CLOSED,
    _BREAKER_HALF_OPEN,
    _BREAKER_OPEN,
)


# ------------------------------------------------------------------ fakes


@dataclass
class FakeResponse:
    status: int
    headers: dict = field(default_factory=dict)


class FakeCM:
    def __init__(self, resp): self._resp = resp
    async def __aenter__(self): return self._resp
    async def __aexit__(self, *a): return False


class FakeSession:
    def __init__(self, script=None):
        # script: list of (status, headers) veya tek (status, headers)
        self.script = list(script) if script else [(200, {})]
        self.calls: list = []

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json})
        if len(self.script) > 1:
            status, headers = self.script.pop(0)
        else:
            status, headers = self.script[0]
        return FakeCM(FakeResponse(status=status, headers=headers))


def _conn():
    c = sqlite3.connect(":memory:")
    return c


def _cfg(**over):
    base = dict(
        telegram_bot_token="T",
        telegram_chat_id="C",
        rate_limit_s=30,
        dedup_window_s=60,
        retry_max=3,
        breaker_fail_threshold=5,
        breaker_open_s=60,
    )
    base.update(over)
    return AlertConfig(**base)


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t
    def __call__(self):
        return self.t
    def advance(self, dt):
        self.t += dt


# ------------------------------------------------------------------ config


def test_config_validate_requires_dedup_ge_rate():
    with pytest.raises(ValueError):
        AlertConfig(
            telegram_bot_token="T", telegram_chat_id="C",
            rate_limit_s=60, dedup_window_s=30,
        ).validate()


def test_config_validate_requires_channel():
    with pytest.raises(ValueError):
        AlertConfig(rate_limit_s=30, dedup_window_s=60).validate()


def test_config_validate_negative_int():
    with pytest.raises(ValueError):
        AlertConfig(
            telegram_bot_token="T", telegram_chat_id="C",
            retry_max=-1,
        ).validate()


def test_config_from_env_reads_ints(monkeypatch):
    env = {
        "MIKOV2_ALERT_TELEGRAM_TOKEN": "T",
        "MIKOV2_ALERT_TELEGRAM_CHAT_ID": "C",
        "MIKOV2_ALERT_BATCH_SIZE": "7",
        "MIKOV2_ALERT_RATE_LIMIT_S": "30",
        "MIKOV2_ALERT_DEDUP_WINDOW_S": "60",
    }
    cfg = config_from_env(env)
    assert cfg.batch_size == 7
    assert cfg.rate_limit_s == 30


def test_config_from_env_rejects_bad_int():
    env = {
        "MIKOV2_ALERT_TELEGRAM_TOKEN": "T",
        "MIKOV2_ALERT_TELEGRAM_CHAT_ID": "C",
        "MIKOV2_ALERT_BATCH_SIZE": "notint",
    }
    with pytest.raises(ValueError):
        config_from_env(env)


# ------------------------------------------------------------------ emit


def test_emit_info_writes_delivered_row():
    conn = _conn()
    agent = AlertAgent(_cfg(), conn, FakeSession())
    conn.execute(
        "CREATE TABLE alert_events(id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts_ms INTEGER, event_type TEXT, severity TEXT, symbol TEXT,"
        " payload TEXT, delivery_status TEXT, correlation_id TEXT,"
        " source_seq INTEGER, exchange_ts_ms INTEGER,"
        " created_at_ms INTEGER, attempts INTEGER DEFAULT 0,"
        " last_error TEXT)"
    )
    conn.commit()
    agent._conn.execute  # noqa
    ev = asyncio.run(agent.emit("SWEEP", {"symbol": "BTC_USDT"}))
    row = conn.execute(
        "SELECT delivery_status FROM alert_events WHERE id=?", (ev,)
    ).fetchone()
    assert row[0] == "delivered"
    assert agent.metrics["info_logged"] == 1


def test_emit_critical_queues_and_sets_wake():
    conn = _conn()
    agent = AlertAgent(_cfg(), conn, FakeSession())
    agent._conn.execute(
        "CREATE TABLE alert_events(id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts_ms INTEGER, event_type TEXT, severity TEXT, symbol TEXT,"
        " payload TEXT, delivery_status TEXT, correlation_id TEXT,"
        " source_seq INTEGER, exchange_ts_ms INTEGER,"
        " created_at_ms INTEGER, attempts INTEGER DEFAULT 0,"
        " last_error TEXT)"
    )
    conn.commit()
    asyncio.run(agent.emit("CRITICAL_ALERT", {"symbol": "BTC_USDT"}))
    assert len(agent._critical_queue) == 1
    assert agent.metrics["critical_queued"] == 1


def test_emit_warning_buffers_and_dedup_merges():
    conn = _conn()
    clock = FakeClock()
    agent = AlertAgent(_cfg(), conn, FakeSession(), clock=clock)
    agent._conn.execute(
        "CREATE TABLE alert_events(id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts_ms INTEGER, event_type TEXT, severity TEXT, symbol TEXT,"
        " payload TEXT, delivery_status TEXT, correlation_id TEXT,"
        " source_seq INTEGER, exchange_ts_ms INTEGER,"
        " created_at_ms INTEGER, attempts INTEGER DEFAULT 0,"
        " last_error TEXT)"
    )
    conn.commit()
    asyncio.run(agent.emit("TRIGGER", {"symbol": "BTC_USDT"}))
    asyncio.run(agent.emit("TRIGGER", {"symbol": "BTC_USDT"}))
    assert len(agent._warning_buffer) == 1
    _, _, count = agent._warning_buffer[0]
    assert count == 2
    assert agent.metrics["dedup_merged"] == 1


def test_dedup_expires_after_window():
    conn = _conn()
    clock = FakeClock()
    agent = AlertAgent(_cfg(), conn, FakeSession(), clock=clock)
    agent._conn.execute(
        "CREATE TABLE alert_events(id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts_ms INTEGER, event_type TEXT, severity TEXT, symbol TEXT,"
        " payload TEXT, delivery_status TEXT, correlation_id TEXT,"
        " source_seq INTEGER, exchange_ts_ms INTEGER,"
        " created_at_ms INTEGER, attempts INTEGER DEFAULT 0,"
        " last_error TEXT)"
    )
    conn.commit()
    asyncio.run(agent.emit("TRIGGER", {"symbol": "BTC_USDT"}))
    clock.advance(120)
    asyncio.run(agent.emit("TRIGGER", {"symbol": "BTC_USDT"}))
    assert len(agent._warning_buffer) == 2


def test_emit_unknown_event_defaults_warning():
    conn = _conn()
    agent = AlertAgent(_cfg(), conn, FakeSession())
    agent._conn.execute(
        "CREATE TABLE alert_events(id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts_ms INTEGER, event_type TEXT, severity TEXT, symbol TEXT,"
        " payload TEXT, delivery_status TEXT, correlation_id TEXT,"
        " source_seq INTEGER, exchange_ts_ms INTEGER,"
        " created_at_ms INTEGER, attempts INTEGER DEFAULT 0,"
        " last_error TEXT)"
    )
    conn.commit()
    asyncio.run(agent.emit("NEVER_HEARD_OF", {"symbol": "X"}))
    assert len(agent._warning_buffer) == 1


# ------------------------------------------------------------------ drain / breaker


async def _mk_agent(cfg=None, session=None):
    conn = _conn()
    cfg = cfg or _cfg()
    agent = AlertAgent(cfg, conn, session or FakeSession())
    await agent.start()
    return agent


def test_critical_drain_delivered():
    async def _run():
        agent = await _mk_agent()
        await agent.emit("CRITICAL_ALERT", {"symbol": "BTC_USDT"})
        await agent._drain_once()
        rows = agent._conn.execute(
            "SELECT delivery_status FROM alert_events"
        ).fetchall()
        assert rows[0][0] == "delivered"
        assert agent.metrics["delivered"] == 1
        await agent.stop()
    asyncio.run(_run())


def test_breaker_opens_after_five_final_fails():
    async def _run():
        session = FakeSession([(500, {})])
        agent = await _mk_agent(session=session)
        for _ in range(5):
            await agent.emit("CRITICAL_ALERT", {"symbol": "BTC_USDT"})
            await agent._drain_once()
        assert agent.breaker_state == _BREAKER_OPEN
        assert agent.metrics["breaker_open_count"] == 1
        await agent.stop()
    asyncio.run(_run())


def test_half_open_success_closes_breaker():
    async def _run():
        clock = FakeClock()
        session = FakeSession([(500, {})])
        agent = AlertAgent(_cfg(), _conn(), session, clock=clock)
        await agent.start()
        for _ in range(5):
            await agent.emit("CRITICAL_ALERT", {"symbol": "BTC_USDT"})
            await agent._drain_once()
        assert agent.breaker_state == _BREAKER_OPEN
        # 60s geç → HALF_OPEN'a geçecek; session artık success dönüyor
        clock.advance(61)
        session.script = [(200, {})]
        await agent.emit("CRITICAL_ALERT", {"symbol": "BTC_USDT"})
        await agent._drain_once()
        assert agent.breaker_state == _BREAKER_CLOSED
        await agent.stop()
    asyncio.run(_run())


def test_half_open_failure_reopens_breaker():
    async def _run():
        clock = FakeClock()
        session = FakeSession([(500, {})])
        agent = AlertAgent(_cfg(), _conn(), session, clock=clock)
        await agent.start()
        for _ in range(5):
            await agent.emit("CRITICAL_ALERT", {"symbol": "BTC_USDT"})
            await agent._drain_once()
        assert agent.breaker_state == _BREAKER_OPEN
        clock.advance(61)
        # 5 drain sonrası satırlar 'failed' (pending CRITICAL yok).
        # HALF_OPEN testinin deneyeceği yeni bir pending satır üret.
        await agent.emit("CRITICAL_ALERT", {"symbol": "BTC_USDT"})
        await agent._drain_once()
        assert agent.breaker_state == _BREAKER_OPEN
        await agent.stop()
    asyncio.run(_run())


def test_429_retry_after_does_not_count_as_breaker_fail():
    async def _run():
        # 2 kez 429, sonra başarılı
        session = FakeSession([
            (429, {"Retry-After": "0"}),
            (429, {"Retry-After": "0"}),
            (200, {}),
        ])
        sleeps: list = []

        async def _fake_sleep(s):
            sleeps.append(s)

        agent = AlertAgent(
            _cfg(), _conn(), session, sleep_fn=_fake_sleep
        )
        await agent.start()
        await agent.emit("CRITICAL_ALERT", {"symbol": "BTC_USDT"})
        await agent._drain_once()
        assert agent.breaker_state == _BREAKER_CLOSED
        assert agent.metrics["delivered"] == 1
        assert len(sleeps) >= 2
        await agent.stop()
    asyncio.run(_run())


def test_optimistic_lock_prevents_double_send():
    async def _run():
        agent = await _mk_agent()
        await agent.emit("CRITICAL_ALERT", {"symbol": "BTC_USDT"})
        # İlk drain gönderir
        await agent._drain_once()
        # İkinci drain boş kuyrukla döner
        await agent._drain_once()
        assert agent.metrics["delivered"] == 1
        await agent.stop()
    asyncio.run(_run())


def test_retry_max_exhaustion_marks_failed():
    async def _run():
        session = FakeSession([(500, {})])
        agent = AlertAgent(
            _cfg(retry_max=3, breaker_fail_threshold=5),
            _conn(), session,
        )
        await agent.start()
        await agent.emit("CRITICAL_ALERT", {"symbol": "BTC_USDT"})
        await agent._drain_once()
        row = agent._conn.execute(
            "SELECT delivery_status, attempts FROM alert_events"
        ).fetchone()
        assert row[0] == "failed"
        assert row[1] >= 3
        await agent.stop()
    asyncio.run(_run())


def test_batch_flush_when_size_reached():
    async def _run():
        agent = await _mk_agent(cfg=_cfg(batch_size=2))
        await agent.emit("TRIGGER", {"symbol": "BTC_USDT"})
        await agent.emit("ENTRY", {"symbol": "BTC_USDT"})
        await agent._drain_once()
        rows = agent._conn.execute(
            "SELECT delivery_status FROM alert_events"
        ).fetchall()
        assert all(r[0] == "delivered" for r in rows)
        assert agent.metrics["delivered"] == 2
        await agent.stop()
    asyncio.run(_run())


def test_batch_flush_on_window():
    async def _run():
        clock = FakeClock()
        agent = AlertAgent(
            _cfg(batch_size=10, batch_window_s=5),
            _conn(), FakeSession(), clock=clock,
        )
        await agent.start()
        await agent.emit("TRIGGER", {"symbol": "BTC_USDT"})
        clock.advance(6)
        await agent._drain_once()
        row = agent._conn.execute(
            "SELECT delivery_status FROM alert_events"
        ).fetchone()
        assert row[0] == "delivered"
        await agent.stop()
    asyncio.run(_run())


def test_startup_sweeps_expired_pending():
    conn = _conn()
    agent = AlertAgent(_cfg(pending_ttl_s=1), conn, FakeSession())
    run_migration_test(conn)
    # Çok eski pending row
    conn.execute(
        "INSERT INTO alert_events(ts_ms,event_type,severity,created_at_ms,"
        " delivery_status) VALUES(?,?,?,?,?)",
        (1, "TRIGGER", "WARNING", 1, "pending"),
    )
    conn.commit()
    agent._startup_expired_sweep()
    row = conn.execute(
        "SELECT delivery_status FROM alert_events"
    ).fetchone()
    assert row[0] == "expired"


def run_migration_test(conn):
    from src.alerting.migration import run_migration
    run_migration(conn)


def test_send_direct_triggers_drain():
    async def _run():
        agent = await _mk_agent()
        await agent.send_direct("CRITICAL_ALERT", {"symbol": "BTC_USDT"})
        assert agent.metrics["delivered"] >= 1
        await agent.stop()
    asyncio.run(_run())