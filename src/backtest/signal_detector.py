# YAMA Y-353: DI, no global
# REV8: ICT-style signal detection on 5s candles

"""
Signal detector - converts 1s OHLCV into 5s candles and detects:
  SWEEP_UP / SWEEP_DOWN       (liquidity sweep)
  MSS_UP   / MSS_DOWN          (market structure shift)
  FVG_BULLISH / FVG_BEARISH    (fair value gap)
  OTE_LONG / OTE_SHORT         (optimal trade entry zone)
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from enum import Enum

from .replay_transport import OHLCVEvent

logger = logging.getLogger(__name__)


class SignalKind(str, Enum):
    SWEEP_UP = "SWEEP_UP"
    SWEEP_DOWN = "SWEEP_DOWN"
    MSS_UP = "MSS_UP"
    MSS_DOWN = "MSS_DOWN"
    FVG_BULLISH = "FVG_BULLISH"
    FVG_BEARISH = "FVG_BEARISH"
    OTE_LONG = "OTE_LONG"
    OTE_SHORT = "OTE_SHORT"


@dataclass(frozen=True, slots=True)
class Candle5s:
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
class Signal:
    kind: SignalKind
    ts_ms: int
    price: float
    size: float = 0.0
    details: dict | None = None


@dataclass(frozen=True, slots=True)
class DetectorConfig:
    candle_seconds: int = 5
    sweep_lookback: int = 20
    sweep_wick_ratio: float = 0.6
    mss_lookback: int = 10
    fvg_min_size_pct: float = 0.0005
    ote_low: float = 0.62
    ote_high: float = 0.79
    ote_lookback: int = 20
    max_history: int = 300


class SignalDetector:
    def __init__(self, config: DetectorConfig):
        self._cfg = config
        self._active_sec: int | None = None
        self._active: dict | None = None
        self._candles: deque[Candle5s] = deque(maxlen=config.max_history)

    # -------------------------------------------------- feed

    def feed_ohlcv_1s(self, ev: OHLCVEvent) -> list[Signal]:
        cfg = self._cfg
        csec = cfg.candle_seconds
        bucket_sec = (ev.sec // csec) * csec
        out: list[Signal] = []

        if self._active_sec is None:
            self._active = self._new_bucket(bucket_sec, ev)
            self._active_sec = bucket_sec
            return out

        if bucket_sec > self._active_sec:
            self._finalize_active()
            out = self._detect_on_last()
            self._active = self._new_bucket(bucket_sec, ev)
            self._active_sec = bucket_sec
            return out

        if bucket_sec < self._active_sec:
            # out-of-order, drop
            return out

        b = self._active
        if b is None:
            return out
        if ev.high > b["high"]:
            b["high"] = ev.high
        if ev.low < b["low"]:
            b["low"] = ev.low
        b["close"] = ev.close
        b["buy_vol"] += ev.buy_vol
        b["sell_vol"] += ev.sell_vol
        b["trade_count"] += ev.trade_count
        return out

    def flush(self) -> list[Signal]:
        if self._active is None:
            return []
        self._finalize_active()
        return self._detect_on_last()

    # -------------------------------------------------- internal

    def _new_bucket(self, sec: int, ev: OHLCVEvent) -> dict:
        return {
            "sec": sec,
            "ts_ms": sec * 1000,
            "open": ev.open,
            "high": ev.high,
            "low": ev.low,
            "close": ev.close,
            "buy_vol": ev.buy_vol,
            "sell_vol": ev.sell_vol,
            "trade_count": ev.trade_count,
        }

    def _finalize_active(self) -> None:
        b = self._active
        if b is None:
            return
        self._candles.append(
            Candle5s(
                sec=b["sec"],
                ts_ms=b["ts_ms"],
                open=b["open"],
                high=b["high"],
                low=b["low"],
                close=b["close"],
                buy_vol=b["buy_vol"],
                sell_vol=b["sell_vol"],
                trade_count=b["trade_count"],
            )
        )
        self._active = None

    def _detect_on_last(self) -> list[Signal]:
        if not self._candles:
            return []
        c = self._candles[-1]
        out: list[Signal] = []
        out.extend(self._detect_sweep(c))
        out.extend(self._detect_mss(c))
        out.extend(self._detect_fvg())
        out.extend(self._detect_ote(c))
        return out

    # -------------------------------------------------- detectors

    def _detect_sweep(self, c: Candle5s) -> list[Signal]:
        cfg = self._cfg
        if len(self._candles) < cfg.sweep_lookback + 1:
            return []
        window = list(self._candles)[-cfg.sweep_lookback - 1 : -1]
        if not window:
            return []
        prev_high = max(x.high for x in window)
        prev_low = min(x.low for x in window)
        rng = c.high - c.low
        if rng <= 0:
            return []
        body_top = max(c.open, c.close)
        body_bot = min(c.open, c.close)
        wick_up = c.high - body_top
        wick_down = body_bot - c.low
        out: list[Signal] = []
        if c.high > prev_high and c.close < prev_high:
            if wick_up / rng >= cfg.sweep_wick_ratio:
                out.append(Signal(
                    kind=SignalKind.SWEEP_UP,
                    ts_ms=c.ts_ms,
                    price=c.high,
                    size=c.high - prev_high,
                ))
        if c.low < prev_low and c.close > prev_low:
            if wick_down / rng >= cfg.sweep_wick_ratio:
                out.append(Signal(
                    kind=SignalKind.SWEEP_DOWN,
                    ts_ms=c.ts_ms,
                    price=c.low,
                    size=prev_low - c.low,
                ))
        return out

    def _detect_mss(self, c: Candle5s) -> list[Signal]:
        cfg = self._cfg
        if len(self._candles) < cfg.mss_lookback + 1:
            return []
        window = list(self._candles)[-cfg.mss_lookback - 1 : -1]
        if not window:
            return []
        hi = max(x.high for x in window)
        lo = min(x.low for x in window)
        mid = (hi + lo) / 2.0
        prev = self._candles[-2]
        out: list[Signal] = []
        if prev.close <= mid and c.close > mid:
            out.append(Signal(
                kind=SignalKind.MSS_UP,
                ts_ms=c.ts_ms,
                price=c.close,
                size=c.close - mid,
            ))
        if prev.close >= mid and c.close < mid:
            out.append(Signal(
                kind=SignalKind.MSS_DOWN,
                ts_ms=c.ts_ms,
                price=c.close,
                size=mid - c.close,
            ))
        return out

    def _detect_fvg(self) -> list[Signal]:
        cfg = self._cfg
        if len(self._candles) < 3:
            return []
        c1 = self._candles[-3]
        c2 = self._candles[-2]
        c3 = self._candles[-1]
        out: list[Signal] = []
        if c3.low > c1.high:
            size = c3.low - c1.high
            if size / c2.close >= cfg.fvg_min_size_pct:
                out.append(Signal(
                    kind=SignalKind.FVG_BULLISH,
                    ts_ms=c3.ts_ms,
                    price=(c1.high + c3.low) / 2.0,
                    size=size,
                ))
        if c3.high < c1.low:
            size = c1.low - c3.high
            if size / c2.close >= cfg.fvg_min_size_pct:
                out.append(Signal(
                    kind=SignalKind.FVG_BEARISH,
                    ts_ms=c3.ts_ms,
                    price=(c1.low + c3.high) / 2.0,
                    size=size,
                ))
        return out

    def _detect_ote(self, c: Candle5s) -> list[Signal]:
        cfg = self._cfg
        if len(self._candles) < cfg.ote_lookback + 1:
            return []
        window = list(self._candles)[-cfg.ote_lookback - 1 : -1]
        if not window:
            return []
        hi = max(x.high for x in window)
        lo = min(x.low for x in window)
        span = hi - lo
        if span <= 0:
            return []
        out: list[Signal] = []
        long_top = hi - cfg.ote_low * span
        long_bot = hi - cfg.ote_high * span
        if long_bot <= c.close <= long_top:
            out.append(Signal(
                kind=SignalKind.OTE_LONG, ts_ms=c.ts_ms, price=c.close, size=span
            ))
        short_bot = lo + cfg.ote_low * span
        short_top = lo + cfg.ote_high * span
        if short_bot <= c.close <= short_top:
            out.append(Signal(
                kind=SignalKind.OTE_SHORT, ts_ms=c.ts_ms, price=c.close, size=span
            ))
        return out

    # -------------------------------------------------- state

    @property
    def candle_count(self) -> int:
        return len(self._candles)

    @property
    def active_sec(self) -> int | None:
        return self._active_sec