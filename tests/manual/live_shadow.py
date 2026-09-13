"""
Manual live shadow runner - MEXC WS + L2 reconstruction + DB write + dashboard.

Bu script production'da calismaz. MEXC canli verisini cekip:
  - L2 book'u reconstruct eder
  - Basit whale tespit yapip DB'ye yazar
  - 60s'de equity snapshot yazar
  - aiohttp.web dashboard'i ayni process'te ayaga kaldirir

Usage:
    python -m tests.manual.live_shadow --symbol BTC_USDT --duration 600
    python -m tests.manual.live_shadow --symbol BTC_USDT --dashboard --port 8090

Ctrl+C ile temiz kapanis.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from pathlib import Path

import aiohttp

from src.data_layer.l2_buffer import L2Buffer
from src.data_layer.mexc_rest import MEXCRestClient, MEXCRestError
from src.data_layer.mexc_ws import MEXCWSClient
from src.data_layer.seq import SeqMode, SequenceValidator
from src.dashboard.app import DashboardApp, DashboardConfig
from src.dashboard.routes import DashboardRoutes, RoutesConfig
from src.storage.equity_tracker import EquityTracker, EquityTrackerConfig
from src.storage.mark_price_cache import MarkPriceCache
from src.storage.sqlite_writer import SqliteWriter, SqliteWriterConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("live_shadow")


# --------------------------------------------------------------------- whale config

WHALE_OI_MIN_USD = 50_000.0
WHALE_MIN_LIFETIME_MS = 3000
WHALE_MIN_FILL_RATIO = 0.30
WHALE_MAX_FILL_RATIO_SPOOF = 0.10
EQUITY_TICK_S = 60.0


# --------------------------------------------------------------------- runner


class LiveShadow:
    def __init__(
        self,
        symbol: str,
        duration_s: int,
        db_path: Path,
        dashboard: bool,
        port: int,
    ) -> None:
        self.symbol = symbol
        self.duration_s = duration_s
        self.db_path = db_path
        self.run_dashboard = dashboard
        self.port = port

        self.books: dict = {}
        self.l2 = L2Buffer(self.books)
        self.seq = SequenceValidator({}, {}, mode=SeqMode.MEXC)
        self.mark_cache = MarkPriceCache()

        self.sqlite: SqliteWriter | None = None
        self.equity: EquityTracker | None = None
        self.dashboard: DashboardApp | None = None

        self.current_epoch = 1
        self.synced = False
        self.snapshot_version = 0
        self.last_applied_version = 0
        self.pending: list[dict] = []

        self.metrics = {
            "pushes": 0,
            "valid": 0,
            "gaps": 0,
            "resyncs": 0,
            "stale": 0,
            "whales": 0,
        }
        self._shutdown = asyncio.Event()

    # ---------------------------------------------------------------- setup

    async def setup(self) -> None:
        self.sqlite = SqliteWriter(
            SqliteWriterConfig(db_path=self.db_path), asyncio.Lock()
        )
        await self.sqlite.connect()

        self.equity = EquityTracker(
            EquityTrackerConfig(base_balance=1000.0),
            self.sqlite,
            self.mark_cache,
            asyncio.Lock(),
        )

        if self.run_dashboard:
            routes = DashboardRoutes(
                RoutesConfig(),
                self.sqlite,
                asyncio.Lock(),
            )
            self.dashboard = DashboardApp(
                DashboardConfig(host="127.0.0.1", port=self.port),
                routes,
                self.sqlite,
                asyncio.Lock(),
            )
            await self.dashboard.start()
            logger.warning(
                "dashboard started http://127.0.0.1:%d/", self.port
            )

    # ---------------------------------------------------------------- ws callback

    def _parse_diffs(self, data: dict) -> list:
        diffs = []
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
        book = self.l2.get_book(self.symbol)
        if book is None:
            return
        diffs = self._parse_diffs(data)
        if not diffs:
            return
        self.l2.apply_batch(
            self.symbol,
            diffs,
            batch_epoch=book.seq_epoch.get(self.symbol, 0),
        )
        self.metrics["valid"] += 1

    def _apply_snapshot(self, snap: dict) -> None:
        book = self.l2.create_book(self.symbol)
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

    async def on_depth(self, symbol: str, data: dict) -> None:
        if symbol != self.symbol:
            return
        version = data.get("version")
        if version is None:
            return
        version = int(version)

        if not self.synced:
            self.pending.append({"version": version, "data": data})
            return

        self.metrics["pushes"] += 1
        result = await self.seq.validate(
            self.symbol, self.current_epoch, first_u=version
        )
        if result.needs_resync:
            self.metrics["gaps"] += 1
            try:
                await self._gap_recover()
            except Exception as e:
                logger.warning("gap recovery failed: %s", e)
            return
        if not result.is_valid:
            if result.is_gap:
                self.metrics["gaps"] += 1
            else:
                self.metrics["stale"] += 1
            return

        self._apply_push(data)
        self.last_applied_version = version

        # track mid-price for mark cache
        book = self.l2.get_book(self.symbol)
        if book is not None and book.bids_len > 0 and book.asks_len > 0:
            mid = (book.bids_price[0] + book.asks_price[0]) / 2.0
            await self.mark_cache.update(
                self.symbol, mid, int(time.time() * 1000)
            )

        # naive whale detection every push (very coarse for demo)
        await self._maybe_whale(book)

    # ---------------------------------------------------------------- whale

    async def _maybe_whale(self, book) -> None:
        if book is None or book.bids_len == 0 or book.asks_len == 0:
            return
        # Use top-of-book volume delta as proxy for demo
        top_bid_qty = float(book.bids_qty[0])
        top_ask_qty = float(book.asks_qty[0])
        oi_delta_proxy = (top_bid_qty + top_ask_qty) * float(book.bids_price[0])
        if oi_delta_proxy < WHALE_OI_MIN_USD:
            return
        # cooldown: don't spam same symbol faster than 5s
        now_ms = int(time.time() * 1000)
        last = getattr(self, "_last_whale_ms", 0)
        if now_ms - last < 5000:
            return
        self._last_whale_ms = now_ms

        is_real = True
        is_spoof = False
        try:
            await self.sqlite.insert_whale_event(
                {
                    "symbol": self.symbol,
                    "band_key": "live_%d" % int(now_ms / 1000),
                    "price": float(book.bids_price[0]),
                    "oi_delta_usd": oi_delta_proxy,
                    "fill_ratio": 0.5,
                    "order_lifetime_ms": 4000,
                    "is_real": is_real,
                    "is_spoof": is_spoof,
                    "trust_score": 1,
                    "exchange_ts_ms": now_ms,
                }
            )
            self.metrics["whales"] += 1
        except Exception as e:
            logger.warning("whale insert failed: %s", e)

    # ---------------------------------------------------------------- bootstrap

    async def _bootstrap(self, rest: MEXCRestClient) -> None:
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and not self.pending:
            await asyncio.sleep(0.05)

        snap = await rest.fetch_snapshot(self.symbol)
        self.snapshot_version = snap["version"]
        self.last_applied_version = snap["version"]
        logger.info(
            "snapshot version=%d buffered=%d first_pending=%s",
            self.snapshot_version,
            len(self.pending),
            self.pending[0]["version"] if self.pending else None,
        )

        self._apply_snapshot(snap)
        await self.seq.set_epoch(self.symbol, self.current_epoch)
        await self.seq.set_last_u(self.symbol, self.snapshot_version, 0)

        # apply buffered in strict order
        for push in sorted(self.pending, key=lambda p: p["version"]):
            v = push["version"]
            if v <= self.last_applied_version:
                continue
            if v != self.last_applied_version + 1 and v - self.last_applied_version > 1:
                # gap; bridge via commits
                break
            self._apply_push(push["data"])
            self.last_applied_version = v

        if self.pending and self.pending[-1]["version"] > self.last_applied_version:
            logger.warning("bootstrap gap, bridging via depth_commits")
            try:
                await self._gap_recover(rest)
            except Exception as e:
                logger.warning("bridge failed: %s", e)

        self.pending.clear()
        self.synced = True
        logger.info("bootstrap complete last_applied=%d", self.last_applied_version)

    async def _gap_recover(self, rest: MEXCRestClient | None = None) -> None:
        if rest is None:
            return
        commits = await rest.fetch_commits(self.symbol, limit=1000)
        applied = 0
        for c in commits:
            v = c["version"]
            if v <= self.last_applied_version:
                continue
            if v != self.last_applied_version + 1:
                break
            diffs = []
            for p, q in c["bids"]:
                diffs.append(("bid", p, q))
            for p, q in c["asks"]:
                diffs.append(("ask", p, q))
            book = self.l2.get_book(self.symbol)
            if book is None:
                break
            if diffs:
                self.l2.apply_batch(
                    self.symbol,
                    diffs,
                    batch_epoch=book.seq_epoch.get(self.symbol, 0),
                )
            self.last_applied_version = v
            applied += 1
        await self.seq.set_last_u(self.symbol, self.last_applied_version, 0)
        self.metrics["resyncs"] += 1
        logger.info("gap recovery applied=%d upto=%d", applied, self.last_applied_version)

    # ---------------------------------------------------------------- main

    async def run(self) -> None:
        await self.setup()
        timeout = aiohttp.ClientTimeout(total=5.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            rest = MEXCRestClient(session)

            ws = MEXCWSClient(
                symbols=[self.symbol],
                on_depth=self.on_depth,
                ping_interval_s=12.0,
                dead_timeout_s=30.0,
            )
            await ws.connect()

            await self._bootstrap(rest)

            start = time.monotonic()
            last_equity_tick = start
            try:
                while time.monotonic() - start < self.duration_s:
                    await asyncio.sleep(5.0)

                    # equity snapshot every 60s
                    if time.monotonic() - last_equity_tick >= EQUITY_TICK_S:
                        await self.equity.snapshot_once()
                        last_equity_tick = time.monotonic()

                    logger.info(
                        "tick pushes=%d valid=%d gaps=%d resyncs=%d stale=%d whales=%d last_v=%d",
                        self.metrics["pushes"],
                        self.metrics["valid"],
                        self.metrics["gaps"],
                        self.metrics["resyncs"],
                        self.metrics["stale"],
                        self.metrics["whales"],
                        self.last_applied_version,
                    )
            finally:
                await ws.close()

        if self.dashboard is not None:
            try:
                await asyncio.wait_for(self.dashboard.stop(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("dashboard stop timed out (SSE clients connected)")
        if self.sqlite is not None:
            await self.sqlite.close()

        logger.warning("final metrics: %s", self.metrics)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTC_USDT")
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--db", default="data/live_shadow.db")
    parser.add_argument("--dashboard", action="store_true")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()

    runner = LiveShadow(
        symbol=args.symbol,
        duration_s=args.duration,
        db_path=Path(args.db),
        dashboard=args.dashboard,
        port=args.port,
    )

    try:
        asyncio.run(runner.run())
    except KeyboardInterrupt:
        logger.warning("interrupted by user")


if __name__ == "__main__":
    main()