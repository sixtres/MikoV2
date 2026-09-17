# YAMA Y-353: DI, no global
# REV8: backtest engine - event dispatch

"""
Backtest engine - dispatches replay events to strategy callbacks.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

from .replay_transport import (
    DepthEvent,
    OHLCVEvent,
    ReplayTransport,
    TickerEvent,
)

logger = logging.getLogger(__name__)

OnOHLCV = Callable[[OHLCVEvent], None]
OnDepth = Callable[[DepthEvent], None]
OnTicker = Callable[[TickerEvent], None]


@dataclass
class BacktestStats:
    events_total: int = 0
    ohlcv_count: int = 0
    depth_count: int = 0
    ticker_count: int = 0
    wall_start_ms: int = 0
    wall_end_ms: int = 0
    wall_elapsed_s: float = 0.0
    callback_errors: int = 0
    errors_by_type: dict = field(default_factory=lambda: Counter())

    def to_dict(self) -> dict:
        return {
            "events_total": self.events_total,
            "ohlcv_count": self.ohlcv_count,
            "depth_count": self.depth_count,
            "ticker_count": self.ticker_count,
            "wall_start_ms": self.wall_start_ms,
            "wall_end_ms": self.wall_end_ms,
            "wall_elapsed_s": round(self.wall_elapsed_s, 3),
            "callback_errors": self.callback_errors,
            "errors_by_type": dict(self.errors_by_type),
        }


class BacktestEngine:
    """
    Event-driven backtest engine.

    Usage:
        engine = BacktestEngine(transport)
        engine.on_ohlcv(my_handler)
        engine.on_depth(my_handler)
        engine.on_ticker(my_handler)
        stats = engine.run(ts_from, ts_to)
    """

    def __init__(self, transport: ReplayTransport) -> None:
        self._transport = transport
        self._on_ohlcv: list[OnOHLCV] = []
        self._on_depth: list[OnDepth] = []
        self._on_ticker: list[OnTicker] = []

    # ------------------------------------------------------------ registration

    def on_ohlcv(self, cb: OnOHLCV) -> None:
        self._on_ohlcv.append(cb)

    def on_depth(self, cb: OnDepth) -> None:
        self._on_depth.append(cb)

    def on_ticker(self, cb: OnTicker) -> None:
        self._on_ticker.append(cb)

    # ------------------------------------------------------------ dispatch

    def _dispatch(self, ev: Any, stats: BacktestStats) -> None:
        if isinstance(ev, OHLCVEvent):
            stats.ohlcv_count += 1
            for cb in self._on_ohlcv:
                try:
                    cb(ev)
                except Exception as e:
                    stats.callback_errors += 1
                    stats.errors_by_type[type(e).__name__] += 1
                    logger.warning("on_ohlcv callback error: %s", e)
        elif isinstance(ev, DepthEvent):
            stats.depth_count += 1
            for cb in self._on_depth:
                try:
                    cb(ev)
                except Exception as e:
                    stats.callback_errors += 1
                    stats.errors_by_type[type(e).__name__] += 1
                    logger.warning("on_depth callback error: %s", e)
        elif isinstance(ev, TickerEvent):
            stats.ticker_count += 1
            for cb in self._on_ticker:
                try:
                    cb(ev)
                except Exception as e:
                    stats.callback_errors += 1
                    stats.errors_by_type[type(e).__name__] += 1
                    logger.warning("on_ticker callback error: %s", e)

    # ------------------------------------------------------------ run

    def run(self, ts_from: int, ts_to: int) -> BacktestStats:
        stats = BacktestStats()
        stats.wall_start_ms = ts_from
        stats.wall_end_ms = ts_to
        t0 = time.monotonic()
        try:
            for ev in self._transport.stream(ts_from, ts_to):
                stats.events_total += 1
                self._dispatch(ev, stats)
        finally:
            stats.wall_elapsed_s = time.monotonic() - t0
        return stats