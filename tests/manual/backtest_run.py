"""
Run backtest over collected SQLite data.

Usage:
    python -m tests.manual.backtest_run --db data/mikov2.sqlite --symbol BTC_USDT
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.backtest.engine import BacktestEngine
from src.backtest.replay_transport import ReplayTransport
from src.backtest.signal_detector import DetectorConfig, SignalDetector
from src.backtest.strategy import Strategy, StrategyConfig


def _fmt_ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
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
    args = p.parse_args()



    db = Path(args.db)
    if not db.exists():
        print("db not found:", db)
        return

    transport = ReplayTransport(db, symbol=args.symbol)
    rng = transport.get_time_range()
    if rng is None:
        print("no data")
        return
    lo, hi = rng
    print("range:", _fmt_ts(lo), "->", _fmt_ts(hi))
    print("span hours:", round((hi - lo) / 1000 / 3600, 2))
    print()

    detector = SignalDetector(DetectorConfig())
    strategy = Strategy(StrategyConfig(
        entry_window_ms=args.entry_window_ms,
        min_whale_trust=0,
        require_sweep=not args.no_require_sweep,
        require_mss=not args.no_require_mss,
        require_fvg=not args.no_require_fvg,
        require_ote=args.require_ote,
        cooldown_ms=args.cooldown_ms,
    ), detector)

    entry_list = []

    def on_ohlcv(ev):
        entries = strategy.on_ohlcv(ev)
        for e in entries:
            entry_list.append(e)

    def on_ticker(ev):
        strategy.on_ticker(ev)

    engine = BacktestEngine(transport)
    engine.on_ohlcv(on_ohlcv)
    engine.on_ticker(on_ticker)

    stats = engine.run(lo, hi)
    strategy.finalize()

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


if __name__ == "__main__":
    main()