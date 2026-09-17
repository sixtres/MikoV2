# YAMA Y-353: DI, no global
# REV8: strategy adapter - combines signals into entry decisions

"""
Strategy adapter - consumes signals from SignalDetector and produces
EntrySignal when required conditions align within a time window.
"""

from __future__ import annotations

import logging
from collections import Counter, deque
from dataclasses import dataclass
from enum import Enum

from .replay_transport import OHLCVEvent, TickerEvent
from .signal_detector import Signal, SignalDetector, SignalKind

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    entry_window_ms: int = 15_000
    min_whale_trust: int = 0
    require_sweep: bool = True
    require_mss: bool = True
    require_fvg: bool = True
    require_ote: bool = False
    cooldown_ms: int = 60_000


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True, slots=True)
class EntrySignal:
    direction: Direction
    ts_ms: int
    price: float
    reason: str
    signals: tuple


class Strategy:
    def __init__(self, config: StrategyConfig, detector: SignalDetector):
        self._cfg = config
        self._detector = detector
        self._recent: deque[tuple[int, Signal]] = deque(maxlen=200)
        self._last_entry_ms: dict[Direction, int] = {}
        self._entries: list[EntrySignal] = []
        self._last_trust: int = 0
        self._last_oi_usdt: float = 0.0
        self._last_funding_rate: float = 0.0
        self.signal_counts: Counter = Counter()

    # -------------------------------------------------- feeds

    def on_ohlcv(self, ev: OHLCVEvent) -> list[EntrySignal]:
        signals = self._detector.feed_ohlcv_1s(ev)
        for s in signals:
            self._recent.append((ev.ts_ms, s))
            self.signal_counts[s.kind.value] += 1
        new_entries = self._try_entry(ev.ts_ms, ev.close)
        self._entries.extend(new_entries)
        return new_entries

    def on_ticker(self, ev: TickerEvent) -> None:
        self._last_oi_usdt = ev.oi_usdt
        self._last_funding_rate = ev.funding_rate

    def finalize(self) -> None:
        signals = self._detector.flush()
        for s in signals:
            self._recent.append((s.ts_ms, s))
            self.signal_counts[s.kind.value] += 1

    # -------------------------------------------------- decision

    def _try_entry(self, ts_ms: int, price: float) -> list[EntrySignal]:
        cfg = self._cfg
        if self._last_trust < cfg.min_whale_trust:
            return []
        window_start = ts_ms - cfg.entry_window_ms
        recent = [(t, s) for t, s in self._recent if t >= window_start]
        if not recent:
            return []

        has_sweep_up = any(s.kind == SignalKind.SWEEP_DOWN for _, s in recent)
        has_sweep_down = any(s.kind == SignalKind.SWEEP_UP for _, s in recent)
        has_mss_up = any(s.kind == SignalKind.MSS_UP for _, s in recent)
        has_mss_down = any(s.kind == SignalKind.MSS_DOWN for _, s in recent)
        has_fvg_bull = any(s.kind == SignalKind.FVG_BULLISH for _, s in recent)
        has_fvg_bear = any(s.kind == SignalKind.FVG_BEARISH for _, s in recent)
        has_ote_long = any(s.kind == SignalKind.OTE_LONG for _, s in recent)
        has_ote_short = any(s.kind == SignalKind.OTE_SHORT for _, s in recent)

        long_ok = (
            (not cfg.require_sweep or has_sweep_up)
            and (not cfg.require_mss or has_mss_up)
            and (not cfg.require_fvg or has_fvg_bull)
            and (not cfg.require_ote or has_ote_long)
        )
        short_ok = (
            (not cfg.require_sweep or has_sweep_down)
            and (not cfg.require_mss or has_mss_down)
            and (not cfg.require_fvg or has_fvg_bear)
            and (not cfg.require_ote or has_ote_short)
        )

        out: list[EntrySignal] = []
        contributing = tuple(s.kind.value for _, s in recent)

        if long_ok:
            last = self._last_entry_ms.get(Direction.LONG, 0)
            if ts_ms - last >= cfg.cooldown_ms:
                self._last_entry_ms[Direction.LONG] = ts_ms
                out.append(EntrySignal(
                    direction=Direction.LONG,
                    ts_ms=ts_ms,
                    price=price,
                    reason="sweep+mss+fvg aligned long",
                    signals=contributing,
                ))
        if short_ok:
            last = self._last_entry_ms.get(Direction.SHORT, 0)
            if ts_ms - last >= cfg.cooldown_ms:
                self._last_entry_ms[Direction.SHORT] = ts_ms
                out.append(EntrySignal(
                    direction=Direction.SHORT,
                    ts_ms=ts_ms,
                    price=price,
                    reason="sweep+mss+fvg aligned short",
                    signals=contributing,
                ))
        return out

    # -------------------------------------------------- accessors

    @property
    def entries(self) -> list[EntrySignal]:
        return list(self._entries)

    @property
    def entry_count(self) -> int:
        return len(self._entries)