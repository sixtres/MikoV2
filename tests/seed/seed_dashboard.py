"""
Seed test data for E2E dashboard smoke test.
"""
import asyncio
import sys
from pathlib import Path

# tests/seed/seed_dashboard.py -> project root 2 üst
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.storage.sqlite_writer import SqliteWriter, SqliteWriterConfig

async def main():
    db_path = Path("data/test_dash.db")
    if db_path.exists():
        db_path.unlink()
    sqlite = SqliteWriter(
        SqliteWriterConfig(db_path=db_path), asyncio.Lock()
    )
    await sqlite.connect()
    print("db fresh:", db_path)

    # 2 open positions
    await sqlite.open_position({
        "position_id": "pos_btc_1",
        "symbol": "BTC_USDT",
        "side": "LONG",
        "opened_at_ms": 1700000000000,
        "avg": 50000.0,
        "qty_open": 0.1,
        "qty_remaining": 0.1,
        "original_planned_entry": 50000.0,
        "original_tp": 52000.0,
        "original_sl": 49000.0,
        "whale_trust_score": 3,
        "universe_status": "IN_TOP5",
    })
    await sqlite.open_position({
        "position_id": "pos_eth_1",
        "symbol": "ETH_USDT",
        "side": "SHORT",
        "opened_at_ms": 1700000100000,
        "avg": 3000.0,
        "qty_open": 1.0,
        "qty_remaining": 1.0,
        "original_planned_entry": 3000.0,
        "whale_trust_score": 2,
        "universe_status": "IN_TOP10",
    })

    # 1 closed position (won)
    await sqlite.open_position({
        "position_id": "pos_sol_1",
        "symbol": "SOL_USDT",
        "side": "LONG",
        "avg": 100.0,
    })
    await sqlite.close_position(
        position_id="pos_sol_1",
        close_reason="TP",
        realized_pnl=12.5,
        fee_total=0.4,
        r_multiple=2.1,
    )

    # 10 whale events
    import random
    for i in range(10):
        await sqlite.insert_whale_event({
            "symbol": random.choice(["BTC_USDT", "ETH_USDT", "SOL_USDT"]),
            "band_key": "band_%d" % i,
            "price": 50000.0 + i * 100,
            "oi_delta_usd": 60000.0 + i * 1000,
            "fill_ratio": 0.3 + i * 0.05,
            "order_lifetime_ms": 4000,
            "is_real": i % 3 != 0,
            "is_spoof": i % 5 == 0,
            "trust_score": i % 4,
            "exchange_ts_ms": 1700000000000 + i * 1000,
        })

    # 30 equity snapshots
    import time
    base_ts = int(time.time() * 1000) - 30 * 60000
    for i in range(30):
        await sqlite.insert_equity_snapshot({
            "ts_ms": base_ts + i * 60000,
            "balance": 1000.0,
            "equity": 1000.0 + i * 0.5 + (i % 5) - 2,
            "unrealized_pnl": (i % 5) - 2,
            "realized_today": 12.5,
            "drawdown_pct": 0.005 if i > 15 else 0.0,
            "open_positions": 2,
        })

    # today's daily stats
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await sqlite.upsert_daily_stats({
        "date_utc": today,
        "start_equity": 1000.0,
        "end_equity": 1012.5,
        "realized_pnl": 12.5,
        "fees": 0.4,
        "trades_count": 1,
        "win_count": 1,
        "loss_count": 0,
    })

    await sqlite.close()
    print("seed done")


if __name__ == "__main__":
    asyncio.run(main())