"""
MEXC Futures shadow runner (manual, live network).

Usage:
    python -m tests.shadow.runner --symbol BTC_USDT --duration 600 --db data/mikov2.sqlite

Bootstrap order:
  1. WS connect, subscribe depth + deal
  2. Wait for first depth push (up to 3s)
  3. Fetch REST snapshot
  4. Discard buffered pushes with version <= snapshot.version
  5. Apply remaining buffered in strict +1 order
  6. If still behind, use depth_commits bridge
  7. Live: depth -> L2Buffer -> 60s SQLite flush
           deal  -> 1s OHLCV USDT-normalized bucket -> SQLite flush
           ticker poll (60s) -> OI + mark + funding -> tickers_snapshot
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sqlite3
import time
from pathlib import Path

import aiohttp

from src.data_layer.l2_buffer import L2Buffer
from src.data_layer.mexc_rest import MEXCRestClient
from src.data_layer.mexc_ws import MEXCWSClient
from src.data_layer.seq import SeqMode, SequenceValidator
from src.data_layer.obi import OBIComputer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("shadow")


class ShadowMetrics:
    def __init__(self) -> None:
        self.buffered_pushes = 0
        self.pushes = 0
        self.gaps = 0
        self.resyncs = 0
        self.stale_drops = 0
        self.valid = 0
        self.obi_samples: list[float] = []
        self.max_bids_len = 0
        self.max_asks_len = 0
        self.trades_in = 0
        self.trades_dropped = 0
        self.trades_unknown_side = 0
        self.trades_late = 0
        self.ohlcv_flushed = 0
        self.tickers_polled = 0
        self.tickers_failed = 0
        self.contract_size = 0.0
        self.start_mono = time.monotonic()

    def uptime_s(self) -> float:
        return time.monotonic() - self.start_mono

    def to_dict(self, symbol: str) -> dict:
        obi_avg = (
            sum(self.obi_samples) / len(self.obi_samples)
            if self.obi_samples
            else 0.0
        )
        return {
            "symbol": symbol,
            "uptime_s": round(self.uptime_s(), 2),
            "pushes": self.pushes,
            "valid": self.valid,
            "gaps": self.gaps,
            "resyncs": self.resyncs,
            "stale_drops": self.stale_drops,
            "obi_samples": len(self.obi_samples),
            "obi_avg": round(obi_avg, 6),
            "max_bids_len": self.max_bids_len,
            "max_asks_len": self.max_asks_len,
            "buffered_pushes": self.buffered_pushes,
            "trades_in": self.trades_in,
            "trades_dropped": self.trades_dropped,
            "trades_unknown_side": self.trades_unknown_side,
            "trades_late": self.trades_late,
            "ohlcv_flushed": self.ohlcv_flushed,
            "tickers_polled": self.tickers_polled,
            "tickers_failed": self.tickers_failed,
            "contract_size": self.contract_size,
        }


class ShadowRunner:
    TICKERS_INTERVAL_S = 60.0

    def __init__(
        self,
        symbol: str,
        duration_s: int,
        db_path: Path | None = None,
    ) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self.symbol = symbol
        self.duration_s = duration_s
        self.metrics = ShadowMetrics()

        self.books: dict = {}
        self.l2_buffer = L2Buffer(self.books)
        self.seq_validator = SequenceValidator({}, {}, mode=SeqMode.MEXC)
        self.obi = OBIComputer(depth=10)

        self.current_epoch = 1
        self.synced = False
        self.snapshot_version = 0
        self.last_applied_version = 0
        self.pending: list[dict] = []

        self._ohlcv_buffer: dict[str, dict] = {}
        self._contract_size: float = 0.0
        self._shutdown_event = asyncio.Event()

        self.rest: MEXCRestClient | None = None
        self.ws: MEXCWSClient | None = None

    # ---------------------------------------------------------------- depth

    def _parse_diffs(self, data: dict) -> list[tuple[str, float, float]]:
        diffs: list[tuple[str, float, float]] = []
        for row in data.get("bids") or []:
            try:
                diffs.append(("bid", float(row[0]), float(row[1])))
            except Exception:
                continue
        for row in data.get("asks") or []:
            try:
                diffs.append(("ask", float(row[0]), float(row[1])))
            except Exception:
                continue
        return diffs

    def _apply_push(self, data: dict) -> None:
        book = self.l2_buffer.get_book(self.symbol)
        if book is None:
            return
        diffs = self._parse_diffs(data)
        if not diffs:
            return
        self.l2_buffer.apply_batch(
            self.symbol, diffs, batch_epoch=book.seq_epoch.get(self.symbol, 0)
        )
        self.metrics.max_bids_len = max(self.metrics.max_bids_len, book.bids_len)
        self.metrics.max_asks_len = max(self.metrics.max_asks_len, book.asks_len)
        try:
            self.metrics.obi_samples.append(self.l2_buffer.get_obi(self.symbol))
        except Exception:
            pass

    def _apply_snapshot(self, snap: dict) -> None:
        book = self.l2_buffer.create_book(self.symbol)
        n_bids = min(len(snap["bids"]), 5000)
        n_asks = min(len(snap["asks"]), 5000)
        for i in range(n_bids):
            book.bids_price[i] = snap["bids"][i][0]
            book.bids_qty[i] = snap["bids"][i][1]
        book.bids_len = n_bids
        for i in range(n_asks):
            book.asks_price[i] = snap["asks"][i][0]
            book.asks_qty[i] = snap["asks"][i][1]
        book.asks_len = n_asks

    # ---------------------------------------------------------------- ws callbacks

    async def on_depth(self, symbol: str, data: dict) -> None:
        if symbol != self.symbol:
            return
        version = data.get("version")
        if version is None:
            return
        version = int(version)

        if not self.synced:
            self.pending.append({"version": version, "data": data})
            self.metrics.buffered_pushes += 1
            return

        self.metrics.pushes += 1
        result = await self.seq_validator.validate(
            self.symbol, self.current_epoch, first_u=version
        )
        if result.needs_resync:
            self.metrics.gaps += 1
            logger.warning(
                "gap live version=%d last=%d pending=%d",
                version,
                result.last_u,
                len(self.pending),
            )
            try:
                await self._gap_recover()
            except Exception as e:
                logger.warning("gap recovery failed: %s", e)
            return
        if not result.is_valid:
            if result.is_gap:
                self.metrics.gaps += 1
            else:
                self.metrics.stale_drops += 1
            return

        self._apply_push(data)
        self.metrics.valid += 1
        self.last_applied_version = version

    async def on_deal(self, symbol: str, trades: list) -> None:
        """Handle push.deal batch -> 1s OHLCV USDT-normalized aggregation."""
        if symbol != self.symbol:
            return
        for t in trades:
            if not isinstance(t, dict):
                self.metrics.trades_dropped += 1
                continue
            try:
                price = float(t["p"])
                contracts = float(t["v"])
                side = int(t["T"])
                ts_ms = int(t["t"])
            except (KeyError, ValueError, TypeError):
                self.metrics.trades_dropped += 1
                continue

            if side not in (1, 2):
                self.metrics.trades_unknown_side += 1
                continue

            usdt_vol = contracts * self._contract_size * price
            if usdt_vol <= 0:
                self.metrics.trades_dropped += 1
                continue

            self.metrics.trades_in += 1
            self._update_ohlcv(symbol, price, usdt_vol, side, ts_ms)

    def _update_ohlcv(
        self, symbol: str, price: float, usdt_vol: float, side: int, ts_ms: int
    ) -> None:
        sec = ts_ms // 1000
        b = self._ohlcv_buffer.get(symbol)

        if b is not None and sec < b["sec"]:
            self.metrics.trades_late += 1
            return

        if b is None or b["sec"] != sec:
            if b is not None:
                self._flush_ohlcv_sync(symbol, b)
            b = {
                "sec": sec,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "buy_vol": 0.0,
                "sell_vol": 0.0,
                "count": 0,
            }
            self._ohlcv_buffer[symbol] = b

        if price > b["high"]:
            b["high"] = price
        if price < b["low"]:
            b["low"] = price
        b["close"] = price
        if side == 1:
            b["buy_vol"] += usdt_vol
        else:
            b["sell_vol"] += usdt_vol
        b["count"] += 1

    def _flush_ohlcv_sync(self, symbol: str, b: dict) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO trades_ohlcv_1s
                (symbol, sec, open, high, low, close,
                 buy_vol, sell_vol, trade_count)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    symbol,
                    b["sec"],
                    b["open"],
                    b["high"],
                    b["low"],
                    b["close"],
                    b["buy_vol"],
                    b["sell_vol"],
                    b["count"],
                ),
            )
            self._conn.commit()
            self.metrics.ohlcv_flushed += 1
        except Exception as e:
            logger.warning("flush_ohlcv failed sec=%d err=%s", b["sec"], e)

    # ---------------------------------------------------------------- tickers poll

    async def _tickers_poll_task(self) -> None:
        """Poll ticker + funding REST every N seconds, store snapshot."""
        while not self._shutdown_event.is_set():
            try:
                ticker = await self.rest.fetch_ticker(self.symbol)
                funding = await self.rest.fetch_funding_rate(self.symbol)
                oi_usdt = (
                    ticker["hold_vol"]
                    * self._contract_size
                    * ticker["last_price"]
                )
                self._insert_ticker_snapshot(ticker, funding, oi_usdt)
                self.metrics.tickers_polled += 1
            except Exception as e:
                self.metrics.tickers_failed += 1
                logger.warning("tickers poll failed: %s", e)

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.TICKERS_INTERVAL_S,
                )
                return
            except asyncio.TimeoutError:
                pass

    def _insert_ticker_snapshot(
        self, ticker: dict, funding: dict, oi_usdt: float
    ) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute(
                """INSERT INTO tickers_snapshot
                (ts_ms, symbol, last_price, fair_price, index_price,
                 hold_vol, oi_usdt, funding_rate, next_settle_ms)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    ticker["ts_ms"],
                    ticker["symbol"],
                    ticker["last_price"],
                    ticker["fair_price"],
                    ticker["index_price"],
                    ticker["hold_vol"],
                    oi_usdt,
                    funding["funding_rate"],
                    funding["next_settle_ms"],
                ),
            )
            self._conn.commit()
        except Exception as e:
            logger.warning("ticker insert failed: %s", e)

    # ---------------------------------------------------------------- bootstrap

    async def _bootstrap(self) -> None:
        assert self.rest is not None
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and not self.pending:
            await asyncio.sleep(0.05)
        logger.info("buffered pushes before snapshot=%d", len(self.pending))

        snap = await self.rest.fetch_snapshot(self.symbol)
        self.snapshot_version = snap["version"]
        self.last_applied_version = snap["version"]

        first_pending = self.pending[0]["version"] if self.pending else None
        last_pending = self.pending[-1]["version"] if self.pending else None
        logger.info(
            "snapshot version=%d first_pending=%s last_pending=%s buffered=%d",
            self.snapshot_version,
            first_pending,
            last_pending,
            len(self.pending),
        )

        self._apply_snapshot(snap)
        await self.seq_validator.set_epoch(self.symbol, self.current_epoch)
        await self.seq_validator.set_last_u(self.symbol, self.snapshot_version, 0)

        target_version = self.snapshot_version + 1
        applied_from_buffer = 0
        remaining: list[dict] = []
        for push in self.pending:
            v = push["version"]
            if v < target_version:
                continue
            if v == target_version:
                self._apply_push(push["data"])
                self.last_applied_version = v
                target_version += 1
                applied_from_buffer += 1
            else:
                remaining.append(push)

        logger.info(
            "bootstrap buffer applied=%d remaining=%d next_expected=%d",
            applied_from_buffer,
            len(remaining),
            target_version,
        )

        if remaining:
            logger.warning(
                "gap between snapshot and buffer, bridging via depth_commits"
            )
            try:
                await self._gap_recover()
            except Exception as e:
                logger.warning("gap bridge failed: %s", e)
                if remaining:
                    oldest = remaining[0]["version"]
                    await self.seq_validator.set_last_u(
                        self.symbol, oldest - 1, 0
                    )
                    self.last_applied_version = oldest - 1

            for push in remaining:
                v = push["version"]
                if v != self.last_applied_version + 1:
                    continue
                self._apply_push(push["data"])
                self.last_applied_version = v

        self.pending.clear()
        self.synced = True
        logger.info(
            "bootstrap complete last_applied=%d", self.last_applied_version
        )

    async def _gap_recover(self) -> None:
        if self.rest is None:
            return
        commits = await self.rest.fetch_commits(self.symbol, limit=1000)
        if not commits:
            logger.warning("gap recovery: no commits returned")
            self.metrics.resyncs += 1
            return
        applied = 0
        for commit in commits:
            v = commit["version"]
            if v <= self.last_applied_version:
                continue
            if v != self.last_applied_version + 1:
                break
            book = self.l2_buffer.get_book(self.symbol)
            if book is None:
                break
            diffs: list[tuple[str, float, float]] = []
            for p, q in commit["bids"]:
                diffs.append(("bid", p, q))
            for p, q in commit["asks"]:
                diffs.append(("ask", p, q))
            if diffs:
                self.l2_buffer.apply_batch(
                    self.symbol,
                    diffs,
                    batch_epoch=book.seq_epoch.get(self.symbol, 0),
                )
            self.last_applied_version = v
            applied += 1

        await self.seq_validator.set_last_u(
            self.symbol, self.last_applied_version, 0
        )
        self.metrics.resyncs += 1
        logger.info(
            "gap recovery applied=%d upto=%d",
            applied,
            self.last_applied_version,
        )

    # ---------------------------------------------------------------- flush

    async def _flush_snapshot(self) -> None:
        """Flush L2 depth snapshot + active OHLCV bucket to SQLite."""
        if self.db_path is None or self._conn is None:
            return

        book = self.l2_buffer.get_book(self.symbol)
        if book is not None:
            snapshot_ts = int(time.time() * 1000)
            version = self.last_applied_version
            bids = [
                (float(book.bids_price[i]), float(book.bids_qty[i]))
                for i in range(min(book.bids_len, 500))
            ]
            asks = [
                (float(book.asks_price[i]), float(book.asks_qty[i]))
                for i in range(min(book.asks_len, 500))
            ]
            try:
                self._conn.execute(
                    """INSERT INTO orderbook_snapshots
                    (timestamp_ms, symbol, version, bids_json, asks_json, depth)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        snapshot_ts,
                        self.symbol,
                        version,
                        json.dumps(bids),
                        json.dumps(asks),
                        len(bids),
                    ),
                )
                self._conn.commit()
                logger.info(
                    "flushed depth ts=%d version=%d depth=%d",
                    snapshot_ts,
                    version,
                    len(bids),
                )
            except Exception as e:
                logger.warning("flush depth failed: %s", e)

        for sym, b in list(self._ohlcv_buffer.items()):
            self._flush_ohlcv_sync(sym, b)

    # ---------------------------------------------------------------- main

    def _setup_db(self) -> None:
        if self.db_path is None:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        except Exception as e:
            logger.warning("pragma failed: %s", e)

        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS orderbook_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ms INTEGER,
                symbol TEXT,
                version INTEGER,
                bids_json TEXT,
                asks_json TEXT,
                depth INTEGER
            )"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS trades_ohlcv_1s (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                sec INTEGER NOT NULL,
                open REAL, high REAL, low REAL, close REAL,
                buy_vol REAL DEFAULT 0,
                sell_vol REAL DEFAULT 0,
                trade_count INTEGER DEFAULT 0,
                UNIQUE(symbol, sec)
            )"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS tickers_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_ms INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                last_price REAL,
                fair_price REAL,
                index_price REAL,
                hold_vol REAL,
                oi_usdt REAL,
                funding_rate REAL,
                next_settle_ms INTEGER
            )"""
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_sec "
            "ON trades_ohlcv_1s(symbol, sec)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_ts "
            "ON orderbook_snapshots(timestamp_ms)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickers_ts "
            "ON tickers_snapshot(ts_ms)"
        )
        self._conn.commit()

    def _install_sigterm(self) -> None:
        try:
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGTERM, self._shutdown_event.set)
        except (NotImplementedError, AttributeError, ValueError):
            pass

    async def run(self) -> dict:
        timeout = aiohttp.ClientTimeout(total=5.0)
        self._setup_db()

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                self.rest = MEXCRestClient(session)

                # contract_size for USDT normalization
                try:
                    self._contract_size = await self.rest.fetch_contract_size(
                        self.symbol
                    )
                    self.metrics.contract_size = self._contract_size
                    logger.warning(
                        "contract_size symbol=%s size=%s",
                        self.symbol,
                        self._contract_size,
                    )
                except Exception as e:
                    logger.warning(
                        "fetch_contract_size failed: %s -> default 0.0001", e
                    )
                    self._contract_size = 0.0001
                    self.metrics.contract_size = self._contract_size

                self.ws = MEXCWSClient(
                    symbols=[self.symbol],
                    on_depth=self.on_depth,
                    on_deal=self.on_deal,
                    ping_interval_s=12.0,
                    dead_timeout_s=30.0,
                )
                await self.ws.connect()
                await self._bootstrap()

                self._install_sigterm()

                # Tickers REST poll (OI + funding)
                asyncio.create_task(self._tickers_poll_task())

                # WS data starvation watchdog
                async def ws_watchdog():
                    while not self._shutdown_event.is_set():
                        await asyncio.sleep(15)
                        if self.ws is None:
                            return
                        last = getattr(self.ws, "_last_data_mono", 0.0)
                        now = asyncio.get_event_loop().time()
                        if last > 0 and now - last > 90.0:
                            logger.warning(
                                "WS data starvation %.1fs, triggering shutdown",
                                now - last,
                            )
                            self._shutdown_event.set()
                            return

                asyncio.create_task(ws_watchdog())

                start = time.monotonic()
                last_flush = time.monotonic()
                try:
                    while (
                        self.duration_s == 0
                        or time.monotonic() - start < self.duration_s
                    ):
                        if self._shutdown_event.is_set():
                            logger.warning("shutdown signal received")
                            break
                        await asyncio.sleep(5.0)
                        logger.info(
                            "tick pushes=%d valid=%d gaps=%d resyncs=%d "
                            "stale=%d trades=%d drop=%d side_bad=%d late=%d "
                            "ohlcv=%d tickers=%d tickers_fail=%d last_v=%d",
                            self.metrics.pushes,
                            self.metrics.valid,
                            self.metrics.gaps,
                            self.metrics.resyncs,
                            self.metrics.stale_drops,
                            self.metrics.trades_in,
                            self.metrics.trades_dropped,
                            self.metrics.trades_unknown_side,
                            self.metrics.trades_late,
                            self.metrics.ohlcv_flushed,
                            self.metrics.tickers_polled,
                            self.metrics.tickers_failed,
                            self.last_applied_version,
                        )

                        if time.monotonic() - last_flush >= 60.0:
                            await self._flush_snapshot()
                            last_flush = time.monotonic()
                            if self._conn is not None:
                                cutoff_ms = int(
                                    (time.time() - 7 * 24 * 3600) * 1000
                                )
                                cutoff_sec = int(time.time() - 7 * 24 * 3600)
                                try:
                                    self._conn.execute(
                                        "DELETE FROM orderbook_snapshots "
                                        "WHERE timestamp_ms < ?",
                                        (cutoff_ms,),
                                    )
                                    self._conn.execute(
                                        "DELETE FROM trades_ohlcv_1s "
                                        "WHERE sec < ?",
                                        (cutoff_sec,),
                                    )
                                    self._conn.execute(
                                        "DELETE FROM tickers_snapshot "
                                        "WHERE ts_ms < ?",
                                        (cutoff_ms,),
                                    )
                                    self._conn.commit()
                                except Exception as e:
                                    logger.warning("cleanup failed: %s", e)
                finally:
                    await self._flush_snapshot()
                    if self.ws is not None:
                        await self.ws.close()
        finally:
            if self._conn is not None:
                self._conn.close()

        return self.metrics.to_dict(self.symbol)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTC_USDT")
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--out", default="shadow_report.json")
    parser.add_argument("--db", default=None, help="SQLite DB path")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None
    runner = ShadowRunner(args.symbol, args.duration, db_path=db_path)
    report = asyncio.run(runner.run())

    out_path = Path(args.out)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("report written %s", out_path)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()