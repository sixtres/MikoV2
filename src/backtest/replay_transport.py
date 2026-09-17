# YAMA Y-353: DI, no global
# REV8: SQLite-backed replay transport for backtest

"""
Replay transport - merges OHLCV/depth/ticker streams from SQLite
into a single chronological event stream.
"""

from __future__ import annotations

import heapq
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True, slots=True)
class OHLCVEvent:
    sec: int
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    buy_vol: float
    sell_vol: float
    trade_count: int


@dataclass(frozen=True, slots=True)
class DepthEvent:
    ts_ms: int
    version: int
    bids: list
    asks: list
    depth: int


@dataclass(frozen=True, slots=True)
class TickerEvent:
    ts_ms: int
    last_price: float
    fair_price: float
    index_price: float
    hold_vol: float
    oi_usdt: float
    funding_rate: float
    next_settle_ms: int


AnyEvent = OHLCVEvent | DepthEvent | TickerEvent


class ReplayTransport:
    """
    Reads 3 tables (trades_ohlcv_1s, orderbook_snapshots, tickers_snapshot)
    and yields events in chronological order.

    Symbols: single-symbol streams assumed (BTC_USDT). Multi-symbol
    extension later by adding symbol filter.
    """

    def __init__(self, db_path: Path, symbol: str = "BTC_USDT") -> None:
        self._db_path = db_path
        self._symbol = symbol

    # ------------------------------------------------------------ generators

    def _ohlcv_gen(
        self, conn: sqlite3.Connection, ts_from: int, ts_to: int
    ) -> Iterator[OHLCVEvent]:
        cur = conn.execute(
            "SELECT sec, open, high, low, close, buy_vol, sell_vol, trade_count "
            "FROM trades_ohlcv_1s "
            "WHERE symbol=? AND sec*1000 >= ? AND sec*1000 <= ? "
            "ORDER BY sec ASC",
            (self._symbol, ts_from, ts_to),
        )
        for row in cur:
            sec = int(row[0])
            yield OHLCVEvent(
                sec=sec,
                ts_ms=sec * 1000,
                open=float(row[1] or 0.0),
                high=float(row[2] or 0.0),
                low=float(row[3] or 0.0),
                close=float(row[4] or 0.0),
                buy_vol=float(row[5] or 0.0),
                sell_vol=float(row[6] or 0.0),
                trade_count=int(row[7] or 0),
            )

    def _depth_gen(
        self, conn: sqlite3.Connection, ts_from: int, ts_to: int
    ) -> Iterator[DepthEvent]:
        cur = conn.execute(
            "SELECT timestamp_ms, version, bids_json, asks_json, depth "
            "FROM orderbook_snapshots "
            "WHERE symbol=? AND timestamp_ms >= ? AND timestamp_ms <= ? "
            "ORDER BY timestamp_ms ASC",
            (self._symbol, ts_from, ts_to),
        )
        for row in cur:
            try:
                bids = json.loads(row[2]) if row[2] else []
                asks = json.loads(row[3]) if row[3] else []
            except Exception:
                bids = []
                asks = []
            yield DepthEvent(
                ts_ms=int(row[0]),
                version=int(row[1] or 0),
                bids=bids,
                asks=asks,
                depth=int(row[4] or 0),
            )

    def _ticker_gen(
        self, conn: sqlite3.Connection, ts_from: int, ts_to: int
    ) -> Iterator[TickerEvent]:
        cur = conn.execute(
            "SELECT ts_ms, last_price, fair_price, index_price, "
            "hold_vol, oi_usdt, funding_rate, next_settle_ms "
            "FROM tickers_snapshot "
            "WHERE symbol=? AND ts_ms >= ? AND ts_ms <= ? "
            "ORDER BY ts_ms ASC",
            (self._symbol, ts_from, ts_to),
        )
        for row in cur:
            yield TickerEvent(
                ts_ms=int(row[0]),
                last_price=float(row[1] or 0.0),
                fair_price=float(row[2] or 0.0),
                index_price=float(row[3] or 0.0),
                hold_vol=float(row[4] or 0.0),
                oi_usdt=float(row[5] or 0.0),
                funding_rate=float(row[6] or 0.0),
                next_settle_ms=int(row[7] or 0),
            )

    # ------------------------------------------------------------ stream

    def stream(self, ts_from: int, ts_to: int) -> Iterator[AnyEvent]:
        """
        Yield events in ascending ts_ms order.

        ts_from, ts_to: inclusive epoch ms bounds.
        """
        conn = sqlite3.connect(
            "file:%s?mode=ro" % str(self._db_path), uri=True
        )
        try:
            a = self._ohlcv_gen(conn, ts_from, ts_to)
            b = self._depth_gen(conn, ts_from, ts_to)
            c = self._ticker_gen(conn, ts_from, ts_to)
            for ev in heapq.merge(a, b, c, key=lambda e: e.ts_ms):
                yield ev
        finally:
            conn.close()

    # ------------------------------------------------------------ range

    def get_time_range(self) -> tuple[int, int] | None:
        """
        Return (min_ms, max_ms) covering all tables for symbol.
        None if no data.
        """
        conn = sqlite3.connect(
            "file:%s?mode=ro" % str(self._db_path), uri=True
        )
        try:
            cur = conn.execute(
                "SELECT MIN(sec), MAX(sec) FROM trades_ohlcv_1s WHERE symbol=?",
                (self._symbol,),
            )
            row = cur.fetchone()
            ohlcv_min = (row[0] * 1000) if row and row[0] is not None else None
            ohlcv_max = (row[1] * 1000) if row and row[1] is not None else None

            cur = conn.execute(
                "SELECT MIN(timestamp_ms), MAX(timestamp_ms) "
                "FROM orderbook_snapshots WHERE symbol=?",
                (self._symbol,),
            )
            row = cur.fetchone()
            depth_min = row[0] if row else None
            depth_max = row[1] if row else None

            cur = conn.execute(
                "SELECT MIN(ts_ms), MAX(ts_ms) "
                "FROM tickers_snapshot WHERE symbol=?",
                (self._symbol,),
            )
            row = cur.fetchone()
            tick_min = row[0] if row else None
            tick_max = row[1] if row else None
        finally:
            conn.close()

        mins = [x for x in (ohlcv_min, depth_min, tick_min) if x is not None]
        maxs = [x for x in (ohlcv_max, depth_max, tick_max) if x is not None]
        if not mins or not maxs:
            return None
        return int(min(mins)), int(max(maxs))