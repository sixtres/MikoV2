"""
    Run backtest over collected SQLite data.

    Usage:
        python -m tests.manual.backtest_run --db data/mikov2.sqlite --symbol BTC_USDT
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dataclasses import asdict, dataclass, fields

from src.backtest.engine import BacktestEngine
from src.backtest.position_sim import (
    PositionSimConfig,
    PositionSimulator,
)
from src.backtest.replay_transport import ReplayTransport
from src.backtest.reporting import (
    EquityPoint,
    build_equity_curve,
    compute_metrics,
    write_equity_csv,
)
from src.backtest.signal_detector import DetectorConfig, SignalDetector
from src.backtest.strategy import Strategy, StrategyConfig


def _fmt_ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


_STRATEGY_FIELDS = {f.name for f in fields(StrategyConfig)}
_SIM_FIELDS = {f.name for f in fields(PositionSimConfig)}


def _parse_config_json(s: str) -> dict:
    try:
        d = json.loads(s)
    except json.JSONDecodeError as e:
        raise SystemExit(f"invalid --config JSON: {e}")
    if not isinstance(d, dict):
        raise SystemExit("--config must be a JSON object")
    return d


def _split_override(d: dict) -> tuple[dict, dict]:
    strat: dict = {}
    sim: dict = {}
    for k, v in d.items():
        if k in _STRATEGY_FIELDS:
            strat[k] = v
        elif k in _SIM_FIELDS:
            sim[k] = v
        else:
            raise SystemExit(f"unknown config field: {k}")
    return strat, sim


def _make_configs(
    args, override: dict | None
) -> tuple[StrategyConfig, PositionSimConfig]:
    strat_ov, sim_ov = _split_override(override or {})
    strat_base = {
        "entry_window_ms": args.entry_window_ms,
        "min_whale_trust": 0,
        "require_sweep": not args.no_require_sweep,
        "require_mss": not args.no_require_mss,
        "require_fvg": not args.no_require_fvg,
        "require_ote": args.require_ote,
        "cooldown_ms": args.cooldown_ms,
    }
    sim_base: dict = {"include_funding": args.include_funding}
    strat_base.update(strat_ov)
    sim_base.update(sim_ov)
    return StrategyConfig(**strat_base), PositionSimConfig(**sim_base)


def _delta(b, a):
    if a is None or b is None:
        return None
    return round(b - a, 4)


def _compare(ma: dict, mb: dict) -> dict:
    return {
        "delta_sharpe": round(
            mb["sharpe_annualized"] - ma["sharpe_annualized"], 4
        ),
        "delta_profit_factor": _delta(
            mb["profit_factor"], ma["profit_factor"]
        ),
        "delta_expectancy_r": round(
            mb["expectancy_r"] - ma["expectancy_r"], 4
        ),
        "delta_max_consecutive_losses": (
            mb["max_consecutive_losses"] - ma["max_consecutive_losses"]
        ),
    }


@dataclass
class _RunResult:
    payload: dict
    equity_curve: list
    trades: list


def _run_once(
    db: Path,
    symbol: str,
    strategy_cfg: StrategyConfig,
    sim_cfg: PositionSimConfig,
    tag: str = "",
) -> _RunResult:
    if tag:
        print(f"=== {tag} ===")

    transport = ReplayTransport(db, symbol=symbol)
    rng = transport.get_time_range()
    if rng is None:
        raise SystemExit("no data")
    lo, hi = rng
    print("range:", _fmt_ts(lo), "->", _fmt_ts(hi))
    print("span hours:", round((hi - lo) / 1000 / 3600, 2))
    print()

    detector = SignalDetector(DetectorConfig())
    strategy = Strategy(strategy_cfg, detector)
    sim = PositionSimulator(sim_cfg)

    entry_list: list = []
    state = {"last_close": 0.0, "last_ts_ms": lo}

    def on_ohlcv(ev):
        state["last_close"] = ev.close
        state["last_ts_ms"] = ev.ts_ms
        sim.on_ohlcv(ev)
        entries = strategy.on_ohlcv(ev)
        for e in entries:
            entry_list.append(e)
            sim.on_entry(e, symbol=symbol)

    def on_ticker(ev):
        strategy.on_ticker(ev)
        sim.on_ticker(ev)

    engine = BacktestEngine(transport)
    engine.on_ohlcv(on_ohlcv)
    engine.on_ticker(on_ticker)
    stats = engine.run(lo, hi)
    strategy.finalize()
    sim.finalize(
        last_ts_ms=state["last_ts_ms"],
        last_price=state["last_close"],
    )

    print("=== engine stats ===")
    for k, v in stats.to_dict().items():
        print("  %s = %s" % (k, v))
    print()

    print("=== signal counts ===")
    for kind, cnt in sorted(strategy.signal_counts.items()):
        print("  %-15s %d" % (kind, cnt))
    print()

    print("=== entries ===")
    print("  total:", len(entry_list))
    for e in entry_list[:30]:
        print("  %s %-5s price=%.2f  ts=%s" % (
            _fmt_ts(e.ts_ms), e.direction.value, e.price, e.ts_ms
        ))
    print()

    trades = sim.trades
    print("=== trades ===")
    print("  total:", len(trades))
    for t in trades[:50]:
        print("  %s %-5s entry=%.2f exit=%.2f R=%.2f pnl=%.2f reason=%s" % (
            _fmt_ts(t.entry_ts_ms), t.direction.value,
            t.entry_price, t.exit_price, t.r_multiple, t.pnl_net,
            t.exit_reason.value,
        ))
    print()

    report = sim.build_report()
    metrics = compute_metrics(trades, sim_cfg.initial_equity)
    equity_curve = build_equity_curve(trades, sim_cfg.initial_equity)

    print("=== report ===")
    for k, v in report.to_dict().items():
        print("  %s = %s" % (k, v))
    print("=== metrics ===")
    for k, v in metrics.to_dict().items():
        print("  %s = %s" % (k, v))
    print()

    payload = {
        "config": {
            "strategy": asdict(strategy_cfg),
            "sim": asdict(sim_cfg),
        },
        "summary": report.to_dict(),
        "metrics": metrics.to_dict(),
        "equity_curve": [p.to_dict() for p in equity_curve],
        "engine": stats.to_dict(),
        "signal_counts": dict(strategy.signal_counts),
        "trades": [t.to_dict() for t in trades],
    }
    return _RunResult(
        payload=payload, equity_curve=equity_curve, trades=trades
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/mikov2.sqlite")
    p.add_argument("--symbol", default="BTC_USDT")
    p.add_argument("--require-ote", action="store_true")
    p.add_argument("--no-require-sweep", action="store_true",
                   help="Disable sweep requirement (default: sweep required)")
    p.add_argument("--no-require-mss", action="store_true",
                   help="Disable MSS requirement (default: MSS required)")
    p.add_argument("--no-require-fvg", action="store_true",
                   help="Disable FVG requirement (default: FVG required)")
    p.add_argument("--entry-window-ms", type=int, default=15_000)
    p.add_argument("--cooldown-ms", type=int, default=60_000)
    p.add_argument("--report", type=str, default="",
                   help="B2d: genişletilmiş rapor JSON (summary + metrics + equity_curve + ...)")
    p.add_argument("--include-funding", action="store_true",
                   help="B2c: funding maliyetini hesaba kat (default kapalı)")
    p.add_argument("--config-a", type=str, default="",
                   help="B2d: JSON override (StrategyConfig/PositionSimConfig alanları)")
    p.add_argument("--config-b", type=str, default="",
                   help="B2d: JSON override (run B); verilirse multi-config karşılaştırma")
    p.add_argument("--equity-csv", type=str, default="",
                   help="B2d: equity curve CSV. Multi-config: <path>.config_a.csv / .config_b.csv")
    args = p.parse_args()

    db = Path(args.db)
    if not db.exists():
        print("db not found:", db)
        return

    over_a = _parse_config_json(args.config_a) if args.config_a else None
    over_b = _parse_config_json(args.config_b) if args.config_b else None
    if over_b is not None and over_a is None:
        raise SystemExit("--config-b requires --config-a")
    multi = over_b is not None

    strat_a, sim_a = _make_configs(args, over_a)
    result_a = _run_once(
        db, args.symbol, strat_a, sim_a,
        tag="config_a" if multi else "",
    )

    if multi:
        strat_b, sim_b = _make_configs(args, over_b)
        result_b = _run_once(db, args.symbol, strat_b, sim_b, tag="config_b")
        report_payload = {
            "config_a": result_a.payload,
            "config_b": result_b.payload,
            "comparison": _compare(
                result_a.payload["metrics"],
                result_b.payload["metrics"],
            ),
        }
    else:
        report_payload = result_a.payload

    if args.report:
        Path(args.report).write_text(
            json.dumps(report_payload, indent=2), encoding="utf-8"
        )
        print()
        print("report written:", args.report)

    if args.equity_csv:
        if multi:
            base = Path(args.equity_csv)
            ext = base.suffix or ".csv"
            path_a = base.with_name(f"{base.stem}.config_a{ext}")
            path_b = base.with_name(f"{base.stem}.config_b{ext}")
            write_equity_csv(path_a, result_a.equity_curve)
            write_equity_csv(path_b, result_b.equity_curve)
            print()
            print("equity csv:", path_a)
            print("equity csv:", path_b)
        else:
            write_equity_csv(args.equity_csv, result_a.equity_curve)
            print()
            print("equity csv:", args.equity_csv)


if __name__ == "__main__":
    main()