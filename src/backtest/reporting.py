# src/backtest/reporting.py
# YAMA Y-353: DI, no global
# REV8: B2d — Backtest extended reporting (DURUM §8)

"""
B2d — Extended backtest reporting.

Computes derived metrics from a list[Trade]:
  - Sharpe (annualized, per-trade returns)
  - Profit factor
  - Expectancy (R)
  - Average holding time
  - Max consecutive losses
  - Equity curve

Kilitli kararlar (DURUM §8):
  SORU B: (A) çoklu config tek JSON iki rapor bloğu
  SORU C: (B) equity curve JSON + CSV; PNG yok

VARSAYIM (PO teyidi bekleniyor):
  - Sharpe yıllıklandırma: trades_per_year = n / span_years; span_years
    = (max_exit_ts - min_entry_ts) / (365*24*3600*1000)
  - risk_free_rate = 0.0
  - Profit factor tanımsız (kayıp trade yok) → None (JSON uyumlu)
  - Sharpe std=0 veya n<2 → 0.0
  - build_equity_curve: trades listesi exit_ts_ms sırasında (position_sim
    _close_position append sırası garanti eder)
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from .position_sim import Trade

_SECONDS_PER_YEAR = 365.0 * 24.0 * 3600.0


@dataclass(frozen=True, slots=True)
class ExtendedMetrics:
    sharpe_annualized: float
    profit_factor: float | None
    expectancy_r: float
    avg_holding_sec: float
    max_consecutive_losses: int

    def to_dict(self) -> dict:
        pf = self.profit_factor
        if pf is not None and (math.isnan(pf) or math.isinf(pf)):
            pf = None
        return {
            "sharpe_annualized": round(self.sharpe_annualized, 4),
            "profit_factor": None if pf is None else round(pf, 4),
            "expectancy_r": round(self.expectancy_r, 4),
            "avg_holding_sec": round(self.avg_holding_sec, 2),
            "max_consecutive_losses": self.max_consecutive_losses,
        }


@dataclass(frozen=True, slots=True)
class EquityPoint:
    ts_ms: int
    equity: float

    def to_dict(self) -> dict:
        return {"ts_ms": self.ts_ms, "equity": round(self.equity, 4)}


def compute_metrics(
    trades: list[Trade],
    initial_equity: float,
) -> ExtendedMetrics:
    n = len(trades)
    if n == 0:
        return ExtendedMetrics(
            sharpe_annualized=0.0,
            profit_factor=None,
            expectancy_r=0.0,
            avg_holding_sec=0.0,
            max_consecutive_losses=0,
        )

    expectancy_r = sum(t.r_multiple for t in trades) / n

    gross_win = sum(t.pnl_net for t in trades if t.pnl_net > 0.0)
    gross_loss = sum(-t.pnl_net for t in trades if t.pnl_net < 0.0)
    if gross_loss > 0.0:
        profit_factor: float | None = gross_win / gross_loss
    else:
        profit_factor = None

    holds = [t.exit_ts_ms - t.entry_ts_ms for t in trades]
    avg_holding_sec = (sum(holds) / n) / 1000.0

    max_streak = 0
    cur = 0
    for t in trades:
        if t.pnl_net < 0.0:
            cur += 1
            if cur > max_streak:
                max_streak = cur
        else:
            cur = 0

    sharpe = _sharpe_annualized(trades, initial_equity)

    return ExtendedMetrics(
        sharpe_annualized=sharpe,
        profit_factor=profit_factor,
        expectancy_r=expectancy_r,
        avg_holding_sec=avg_holding_sec,
        max_consecutive_losses=max_streak,
    )


def _sharpe_annualized(
    trades: list[Trade],
    initial_equity: float,
) -> float:
    n = len(trades)
    if n < 2:
        return 0.0
    eq = float(initial_equity)
    rets: list[float] = []
    for t in trades:
        if eq <= 0.0:
            return 0.0
        rets.append(t.pnl_net / eq)
        eq += t.pnl_net
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    std = math.sqrt(var) if var > 0.0 else 0.0
    if std == 0.0:
        return 0.0
    span_ms = max(t.exit_ts_ms for t in trades) - min(
        t.entry_ts_ms for t in trades
    )
    if span_ms <= 0:
        return 0.0
    span_years = (span_ms / 1000.0) / _SECONDS_PER_YEAR
    if span_years <= 0.0:
        return 0.0
    trades_per_year = n / span_years
    return (mean / std) * math.sqrt(trades_per_year)


def build_equity_curve(
    trades: list[Trade],
    initial_equity: float,
) -> list[EquityPoint]:
    if not trades:
        return []
    eq = float(initial_equity)
    points: list[EquityPoint] = [
        EquityPoint(ts_ms=trades[0].entry_ts_ms, equity=eq)
    ]
    for t in trades:
        eq += t.pnl_net
        points.append(EquityPoint(ts_ms=t.exit_ts_ms, equity=eq))
    return points


def write_equity_csv(path: str | Path, curve: list[EquityPoint]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_ms", "equity"])
        for pt in curve:
            w.writerow([pt.ts_ms, f"{pt.equity:.4f}"])