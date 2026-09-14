"""
MEXC Futures shadow runner (manual, live network).

Usage:
    python -m tests.shadow.runner --symbol BTC_USDT --duration 600

Bootstrap order (correct):
  1. WS connect, subscribe, start buffering pushes
  2. Wait for first push (up to 3s)
  3. Fetch REST snapshot
  4. Discard buffered pushes with version <= snapshot.version
  5. Apply remaining buffered in strict +1 order
  6. If still behind, use depth_commits bridge
  7. Switch to live mode
"""

from __future__ import annotations

import sqlite3
import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

import aiohttp

from src.data_layer.l2_buffer import L2Buffer
from src.data_layer.mexc_rest import MEXCRestClient, MEXCRestError
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
        self.start_mono = time.monotonic()

    def uptime_s(self) -> float:
        return time.monotonic() - self.start_mono

    def to_dict(self, symbol: str) -> dict:
        obi_avg = sum(self.obi_samples) / len(self.obi_samples) if self.obi_samples else 0.0
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
        }


class ShadowRunner:
    def __init__(self, symbol: str, duration_s: int, db_path: Path | None = None) -> None:
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

        self.rest: MEXCRestClient | None = None
        self.ws: MEXCWSClient | None = None

    # ---- helpers ----

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
        import numpy as np

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

    # ---- ws callback ----

    async def on_depth(self, symbol: str, data: dict) -> None:
        if symbol != self.symbol:
            return
        version = data.get("version")
        if version is None:
            return
        version = int(version)

        # Buffering phase: WS connected but snapshot not yet applied.
        # Not counted as a live push.
        if not self.synced:
            self.pending.append({"version": version, "data": data})
            self.metrics.buffered_pushes += 1
            return

        # Live phase only
        self.metrics.pushes += 1

        result = await self.seq_validator.validate(
            self.symbol, self.current_epoch, first_u=version
        )
        if result.needs_resync:
            self.metrics.gaps += 1
            logger.warning(
                "gap live version=%d last=%d pending=%d",
                version, result.last_u, len(self.pending),
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
                logger.debug(
                    "stale version=%d last=%d",
                    version, result.last_u,
                )
            return

        self._apply_push(data)
        self.metrics.valid += 1
        self.last_applied_version = version

    # ---- bootstrap ----

    async def _bootstrap(self) -> None:
        assert self.rest is not None

        # Wait for at least one buffered push
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
            self.snapshot_version, first_pending, last_pending, len(self.pending),
        )

        # Apply snapshot to buffer
        self._apply_snapshot(snap)

        # Set epoch + last_u in validator to snapshot version
        await self.seq_validator.set_epoch(self.symbol, self.current_epoch)
        await self.seq_validator.set_last_u(
            self.symbol, self.snapshot_version, 0
        )

        # Try to align buffered pushes
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
            applied_from_buffer, len(remaining), target_version,
        )

        # If buffer had gap, try depth_commits bridge
        if remaining:
            logger.warning(
                "gap between snapshot and buffer, bridging via depth_commits"
            )
            try:
                await self._gap_recover()
            except Exception as e:
                logger.warning("gap bridge failed: %s", e)
                # If bridge failed, fall back: just re-sync validator to
                # the oldest buffered push to continue live
                if remaining:
                    oldest = remaining[0]["version"]
                    await self.seq_validator.set_last_u(
                        self.symbol, oldest - 1, 0
                    )
                    self.last_applied_version = oldest - 1
                    logger.warning(
                        "bridge failed; skipping to oldest buffered=%d",
                        oldest,
                    )

            # Try to apply remaining buffer after bridge
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
        logger.info(
            "gap recovery commits=%d range=[%d..%d]",
            len(commits), commits[0]["version"], commits[-1]["version"],
        )
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
                    self.symbol, diffs,
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
            applied, self.last_applied_version,
        )


    async def _flush_snapshot(self) -> None:
        """Flush current L2Buffer snapshot to SQLite."""
        if self.db_path is None or self._conn is None:
            return
        
        book = self.l2_buffer.get_book(self.symbol)
        if book is None:
            return
        
        snapshot_ts = int(time.time() * 1000)
        version = self.last_applied_version
        
        # Serialize bids/asks to JSON
        bids = [(float(book.bids_price[i]), float(book.bids_qty[i])) 
                for i in range(min(book.bids_len, 500))]
        asks = [(float(book.asks_price[i]), float(book.asks_qty[i])) 
                for i in range(min(book.asks_len, 500))]
        
        try:
            self._conn.execute(
                """INSERT INTO orderbook_snapshots 
                (timestamp_ms, symbol, version, bids_json, asks_json, depth)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (snapshot_ts, self.symbol, version, 
                json.dumps(bids), json.dumps(asks), len(bids))
            )
            self._conn.commit()
            logger.info("flushed snapshot ts=%d version=%d depth=%d", 
                    snapshot_ts, version, len(bids))
        except Exception as e:
            logger.warning("flush failed: %s", e)
    # ---- main ----

    async def run(self) -> dict:
        timeout = aiohttp.ClientTimeout(total=5.0)
        
        # Connect SQLite if db_path provided
        if self.db_path is not None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), timeout=5.0)
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
            self._conn.commit()
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                self.rest = MEXCRestClient(session)

                # WS FIRST (buffering)
                self.ws = MEXCWSClient(
                    symbols=[self.symbol],
                    on_depth=self.on_depth,
                    ping_interval_s=12.0,
                    dead_timeout_s=30.0,
                )
                await self.ws.connect()

                # Then bootstrap snapshot
                await self._bootstrap()

                start = time.monotonic()
                last_flush = time.monotonic()
                
                try:
                    # Infinite loop if duration_s == 0
                    while self.duration_s == 0 or time.monotonic() - start < self.duration_s:
                        await asyncio.sleep(5.0)
                        logger.info(
                            "tick pushes=%d valid=%d gaps=%d resyncs=%d stale=%d last_v=%d",
                            self.metrics.pushes,
                            self.metrics.valid,
                            self.metrics.gaps,
                            self.metrics.resyncs,
                            self.metrics.stale_drops,
                            self.last_applied_version,
                        )
                        
                        # Periodic flush every 60 seconds
                        if time.monotonic() - last_flush >= 60.0:
                            await self._flush_snapshot()
                            last_flush = time.monotonic()
                            
                            # Cleanup old snapshots (keep last 7 days)
                            if self._conn is not None:
                                cutoff = int((time.time() - 7*24*3600) * 1000)
                                try:
                                    self._conn.execute(
                                        "DELETE FROM orderbook_snapshots WHERE timestamp_ms < ?",
                                        (cutoff,)
                                    )
                                    self._conn.commit()
                                except Exception as e:
                                    logger.warning("cleanup failed: %s", e)
                finally:
                    await self._flush_snapshot()   # <- bu satir
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
    parser.add_argument("--db", default=None, help="SQLite DB path for persistence")
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