# tests/unit/test_backtest_reporting.py
# REV8: B2d — Extended backtest reporting unit tests (DURUM §8)

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.backtest.position_sim import ExitReason, Trade
from src.backtest.reporting import (
    EquityPoint,
    build_equity_curve,
    compute_metrics,
    write_equity_csv,
)
from src.backtest.strategy import Direction


def _mk_trade(
    pnl_net: float,
    *,
    r_multiple: float = 0.0,
    entry_ts_ms: int = 1_000_000,
    exit_ts_ms: int = 1_060_000,
    direction: Direction = Direction.LONG,
) -> Trade:
    return Trade(
        symbol="BTC_USDT",
        direction=direction,
        entry_ts_ms=entry_ts_ms,
        entry_price=100.0,
        qty=1.0,
        sl_price=99.0,
        tp_price=102.0,
        exit_ts_ms=exit_ts_ms,
        exit_price=100.0 + pnl_net,
        exit_reason=ExitReason.TP if pnl_net >= 0 else ExitReason.SL,
        fee_paid=0.0,
        funding_paid=0.0,
        pnl_gross=pnl_net,
        pnl_net=pnl_net,
        r_multiple=r_multiple,
    )


# ---------------------------------------------------------------- metrics


def test_empty_metrics_zero_and_none():
    m = compute_metrics([], 10_000.0)
    d = m.to_dict()
    assert d["sharpe_annualized"] == 0.0
    assert d["profit_factor"] is None
    assert d["expectancy_r"] == 0.0
    assert d["avg_holding_sec"] == 0.0
    assert d["max_consecutive_losses"] == 0


def test_expectancy_is_mean_r():
    trades = [
        _mk_trade(100.0, r_multiple=1.0),
        _mk_trade(-50.0, r_multiple=-1.0),
        _mk_trade(200.0, r_multiple=2.0),
    ]
    m = compute_metrics(trades, 10_000.0)
    assert m.expectancy_r == pytest.approx(2.0 / 3.0)


def test_profit_factor_basic():
    trades = [
        _mk_trade(300.0),
        _mk_trade(-100.0),
    ]
    m = compute_metrics(trades, 10_000.0)
    assert m.profit_factor == pytest.approx(3.0)


def test_profit_factor_none_when_no_losses():
    trades = [_mk_trade(100.0), _mk_trade(50.0)]
    m = compute_metrics(trades, 10_000.0)
    assert m.profit_factor is None


def test_profit_factor_none_when_all_zero():
    trades = [_mk_trade(0.0), _mk_trade(0.0)]
    m = compute_metrics(trades, 10_000.0)
    assert m.profit_factor is None


def test_max_consecutive_losses():
    signs = [1, -1, -1, -1, 1, 1, -1, -1, 1]
    trades = [_mk_trade(100.0 * s) for s in signs]
    m = compute_metrics(trades, 10_000.0)
    assert m.max_consecutive_losses == 3


def test_avg_holding_sec():
    trades = [
        _mk_trade(100.0, entry_ts_ms=0, exit_ts_ms=60_000),
        _mk_trade(-50.0, entry_ts_ms=0, exit_ts_ms=120_000),
    ]
    m = compute_metrics(trades, 10_000.0)
    assert m.avg_holding_sec == pytest.approx(90.0)


def test_sharpe_zero_for_single_trade():
    m = compute_metrics([_mk_trade(100.0)], 10_000.0)
    assert m.sharpe_annualized == 0.0


def test_sharpe_zero_when_std_zero():
    trades = [
        _mk_trade(0.0, entry_ts_ms=0, exit_ts_ms=10_000),
        _mk_trade(0.0, entry_ts_ms=10_000, exit_ts_ms=20_000),
    ]
    m = compute_metrics(trades, 10_000.0)
    assert m.sharpe_annualized == 0.0


def test_sharpe_nonzero_when_variance_exists():
    trades = [
        _mk_trade(100.0, entry_ts_ms=0, exit_ts_ms=10_000),
        _mk_trade(-50.0, entry_ts_ms=10_000, exit_ts_ms=20_000),
        _mk_trade(200.0, entry_ts_ms=20_000, exit_ts_ms=30_000),
    ]
    m = compute_metrics(trades, 10_000.0)
    assert m.sharpe_annualized != 0.0


def test_metrics_to_dict_json_serializable():
    trades = [_mk_trade(100.0), _mk_trade(-50.0)]
    m = compute_metrics(trades, 10_000.0)
    s = json.dumps(m.to_dict())
    assert "Infinity" not in s
    assert "NaN" not in s


def test_metrics_to_dict_handles_infinite_profit_factor():
    trades = [_mk_trade(100.0)]
    m = compute_metrics(trades, 10_000.0)
    d = m.to_dict()
    assert d["profit_factor"] is None
    json.dumps(d)


# ---------------------------------------------------------------- equity curve


def test_equity_curve_empty():
    assert build_equity_curve([], 10_000.0) == []


def test_equity_curve_start_and_end():
    trades = [
        _mk_trade(100.0, entry_ts_ms=100, exit_ts_ms=200),
        _mk_trade(-50.0, entry_ts_ms=200, exit_ts_ms=300),
    ]
    curve = build_equity_curve(trades, 10_000.0)
    assert len(curve) == 3
    assert curve[0].ts_ms == 100
    assert curve[0].equity == 10_000.0
    assert curve[-1].ts_ms == 300
    assert curve[-1].equity == pytest.approx(10_050.0)


def test_equity_curve_ts_monotone():
    trades = [
        _mk_trade(100.0, entry_ts_ms=100, exit_ts_ms=200),
        _mk_trade(-50.0, entry_ts_ms=200, exit_ts_ms=300),
        _mk_trade(30.0, entry_ts_ms=300, exit_ts_ms=400),
    ]
    curve = build_equity_curve(trades, 10_000.0)
    tss = [p.ts_ms for p in curve]
    assert tss == sorted(tss)


# ---------------------------------------------------------------- CSV


def test_write_equity_csv(tmp_path: Path):
    curve = [
        EquityPoint(ts_ms=100, equity=10_000.0),
        EquityPoint(ts_ms=200, equity=10_100.0),
    ]
    p = tmp_path / "sub" / "eq.csv"
    write_equity_csv(p, curve)
    assert p.exists()
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "ts_ms,equity"
    assert lines[1] == "100,10000.0000"
    assert lines[2] == "200,10100.0000"


def test_write_equity_csv_empty(tmp_path: Path):
    p = tmp_path / "eq.csv"
    write_equity_csv(p, [])
    assert p.exists()
    assert p.read_text(encoding="utf-8").strip() == "ts_ms,equity"