# tests/unit/test_b3_5_auto_finalize.py
"""B3.5-AE=A auto-finalize testleri.

Kapsam:
- started_at=0 -> set to now, no trigger
- target_days ulasilmadi -> no trigger
- target_days ulasildi -> trigger: DB done=1 + stop=1, paper.finalize,
  tek COMPLETED emit
- idempotent: ikinci cagri re-emit etmez
- poll+check sirasi: STOPPED emit YOK, yalniz COMPLETED
"""
from __future__ import annotations

import asyncio
import time

from src.observation.state import load_state, update_state


class _FakeAlert:
    def __init__(self) -> None:
        self.emits: list[tuple[str, dict]] = []

    async def emit(self, event_type: str, payload: dict) -> None:
        self.emits.append((event_type, payload))


class _FakePaper:
    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.finalized: bool = False
        self.finalize_kwargs: dict | None = None

    async def on_entry(self, **kw) -> None:
        self.entries.append(kw)

    def get_open_position_qty(self, symbol: str) -> float:
        return 0.0

    def finalize(self, **kw) -> None:
        self.finalized = True
        self.finalize_kwargs = kw


def _make_runner(tmp_path):
    from tests.shadow.runner import ShadowRunner

    runner = ShadowRunner(
        symbols=["BTC_USDT"],
        duration_s=0,
        db_path=tmp_path / "r.sqlite",
    )
    runner._setup_db()
    runner._alert_agent = _FakeAlert()
    runner._paper = _FakePaper()
    return runner


def test_started_at_auto_set_on_first_check(tmp_path):
    runner = _make_runner(tmp_path)
    asyncio.run(runner._check_auto_finalize())
    st = load_state(runner._conn)
    assert st.observation_started_at_ms > 0
    assert st.auto_finalize_done is False
    assert runner._auto_finalized is False
    runner._conn.close()


def test_target_not_reached_no_trigger(tmp_path):
    runner = _make_runner(tmp_path)
    now_ms = int(time.time() * 1000)
    update_state(
        runner._conn,
        observation_started_at_ms=now_ms - 30 * 86_400_000,
        target_days=60,
    )
    asyncio.run(runner._check_auto_finalize())
    st = load_state(runner._conn)
    assert st.auto_finalize_done is False
    assert runner._auto_finalized is False
    assert len(runner._alert_agent.emits) == 0
    runner._conn.close()


def test_target_reached_triggers(tmp_path):
    runner = _make_runner(tmp_path)
    now_ms = int(time.time() * 1000)
    update_state(
        runner._conn,
        observation_started_at_ms=now_ms - 61 * 86_400_000,
        target_days=60,
    )
    asyncio.run(runner._check_auto_finalize())
    st = load_state(runner._conn)
    assert st.auto_finalize_done is True
    assert st.observation_stop is True
    assert st.observation_completed_ms > 0
    assert st.last_transition_reason == "OBSERVATION_COMPLETED"
    assert runner._auto_finalized is True
    assert runner._observation_stopped is True
    assert runner._paper.finalized is True
    assert len(runner._alert_agent.emits) == 1
    assert runner._alert_agent.emits[0][0] == "OBSERVATION_COMPLETED"
    runner._conn.close()


def test_idempotent_no_reemit(tmp_path):
    runner = _make_runner(tmp_path)
    now_ms = int(time.time() * 1000)
    update_state(
        runner._conn,
        observation_started_at_ms=now_ms - 61 * 86_400_000,
        target_days=60,
    )
    asyncio.run(runner._check_auto_finalize())
    first = len(runner._alert_agent.emits)
    asyncio.run(runner._check_auto_finalize())
    assert len(runner._alert_agent.emits) == first
    runner._conn.close()


def test_no_double_stopped_emit(tmp_path):
    """poll once (no-op) + check (COMPLETED) + poll again (no-op)."""
    runner = _make_runner(tmp_path)
    now_ms = int(time.time() * 1000)
    update_state(
        runner._conn,
        observation_started_at_ms=now_ms - 61 * 86_400_000,
        target_days=60,
    )
    asyncio.run(runner._poll_observation_stop())
    asyncio.run(runner._check_auto_finalize())
    asyncio.run(runner._poll_observation_stop())
    event_types = [e[0] for e in runner._alert_agent.emits]
    assert event_types == ["OBSERVATION_COMPLETED"]
    runner._conn.close()


def test_already_done_at_startup(tmp_path):
    """DB'de done=1 ise trigger yok."""
    runner = _make_runner(tmp_path)
    now_ms = int(time.time() * 1000)
    update_state(
        runner._conn,
        observation_started_at_ms=now_ms - 100 * 86_400_000,
        target_days=60,
        auto_finalize_done=1,
    )
    asyncio.run(runner._check_auto_finalize())
    assert runner._auto_finalized is True
    assert len(runner._alert_agent.emits) == 0
    runner._conn.close()