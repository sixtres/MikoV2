# tests/unit/test_b3_5_stop_flag.py
# B3.5-H=C: observation_state.observation_stop poll + yeni entry engelleme.
# 5s micro-trigger loop'a piggyback; SLA <=10s.
"""Stop-flag (H=C) unit + integration testleri."""
from __future__ import annotations

import asyncio

from src.backtest.strategy import Direction
from src.observation.state import set_stop_flag


class _FakePaper:
    def __init__(self) -> None:
        self.entries: list[dict] = []

    async def on_entry(self, **kw) -> None:
        self.entries.append(kw)

    def get_open_position_qty(self, symbol: str) -> float:
        return 0.0


class _FakeAlert:
    def __init__(self) -> None:
        self.emits: list[tuple[str, dict]] = []

    async def emit(self, event_type: str, payload: dict) -> None:
        self.emits.append((event_type, payload))


def _make_runner(tmp_path):
    from tests.shadow.runner import ShadowRunner

    runner = ShadowRunner(
        symbols=["BTC_USDT"],
        duration_s=0,
        db_path=tmp_path / "t.sqlite",
    )
    runner._setup_db()
    # Gercek paper/alert yerine sahte; test sadece wiring'i dogrular.
    runner._paper = _FakePaper()
    runner._alert_agent = _FakeAlert()
    return runner


def test_poll_sets_stopped_true(tmp_path):
    runner = _make_runner(tmp_path)
    set_stop_flag(runner._conn, True)
    runner._poll_observation_stop()
    assert runner._observation_stopped is True
    runner._conn.close()


def test_poll_sets_stopped_false(tmp_path):
    runner = _make_runner(tmp_path)
    set_stop_flag(runner._conn, False)
    runner._poll_observation_stop()
    assert runner._observation_stopped is False
    runner._conn.close()


def test_poll_retains_previous_on_error(tmp_path):
    runner = _make_runner(tmp_path)
    runner._observation_stopped = True
    runner._conn.close()  # sonraki poll'da ProgrammingError beklenir
    runner._poll_observation_stop()
    assert runner._observation_stopped is True  # onceki state korundu


def test_handle_entry_when_not_stopped(tmp_path):
    runner = _make_runner(tmp_path)
    runner._observation_stopped = False
    asyncio.run(
        runner._handle_micro_trigger_entry(
            "BTC_USDT", Direction.LONG, 50000.0, 123
        )
    )
    assert len(runner._paper.entries) == 1
    assert runner._paper.entries[0]["symbol"] == "BTC_USDT"
    assert runner._paper.entries[0]["direction"] == "LONG"
    assert len(runner._alert_agent.emits) == 1
    assert runner._alert_agent.emits[0][0] == "ENTRY"
    runner._conn.close()


def test_handle_entry_when_stopped(tmp_path):
    runner = _make_runner(tmp_path)
    runner._observation_stopped = True
    asyncio.run(
        runner._handle_micro_trigger_entry(
            "BTC_USDT", Direction.LONG, 50000.0, 123
        )
    )
    assert runner._paper.entries == []
    assert runner._alert_agent.emits == []
    runner._conn.close()


def test_flag_flip_reflected(tmp_path):
    runner = _make_runner(tmp_path)
    set_stop_flag(runner._conn, False)
    runner._poll_observation_stop()
    asyncio.run(
        runner._handle_micro_trigger_entry(
            "BTC_USDT", Direction.LONG, 1.0, 1
        )
    )
    assert len(runner._paper.entries) == 1

    set_stop_flag(runner._conn, True)
    runner._poll_observation_stop()
    asyncio.run(
        runner._handle_micro_trigger_entry(
            "BTC_USDT", Direction.LONG, 1.0, 2
        )
    )
    assert len(runner._paper.entries) == 1  # ikinci entry bloklandi
    assert len(runner._alert_agent.emits) == 1
    runner._conn.close()