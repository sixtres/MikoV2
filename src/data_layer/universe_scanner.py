# YAMA Y-267: whale band ±0.5% fingerprint tick_size
# YAMA Y-268: OI USD 50k min, min_oi_usd
# YAMA Y-353: DI, no global
# YAMA Y-358: asyncio.Lock DI
# REV7: Universe scanner - takip modu (Top5/10), hysteresis 5m, flap 3

"""
Universe scanner - tracks Top5/Top10 symbols with hysteresis.

Modes:
  IN_TOP5         - actively traded
  IN_TOP10        - watch, may promote
  OUTSIDE_PENDING - just dropped, waiting 5m hysteresis
  DROPPED         - fully dropped

Score weights (from config):
  oi_change 0.30, liq 0.30, squeeze 0.20, funding 0.10, spread 0.10

No timer here. Supervisor calls refresh() every 30s.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class UniverseStatus(str, Enum):
    IN_TOP5 = "IN_TOP5"
    IN_TOP10 = "IN_TOP10"
    OUTSIDE_PENDING = "OUTSIDE_PENDING"
    DROPPED = "DROPPED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ScannerConfig:
    max_top: int = 5
    max_watch: int = 10
    min_spread_bps: float = 5.0
    max_spread_bps: float = 20.0
    min_oi_usd: float = 50_000_000.0
    hysteresis_ms: int = 300_000
    max_pending_ms: int = 600_000
    flap_threshold: int = 3
    flap_window_ms: int = 300_000
    always_include: tuple = ("BTC_USDT",)
    weight_oi_change: float = 0.30
    weight_liq: float = 0.30
    weight_squeeze: float = 0.20
    weight_funding: float = 0.10
    weight_spread: float = 0.10


@dataclass(slots=True)
class SymbolMetrics:
    symbol: str
    oi_change: float = 0.0
    liq: float = 0.0
    squeeze: float = 0.0
    funding: float = 0.0
    spread_bps: float = 0.0
    oi_usd: float = 0.0


@dataclass(slots=True)
class SymbolState:
    status: UniverseStatus = UniverseStatus.UNKNOWN
    pending_since_ms: int = 0
    flap_count: int = 0
    last_flap_ms: int = 0
    last_score: float = 0.0


class UniverseScanner:
    """
    Universe scanner. Supervisor calls refresh() every 30s with metrics.
    """

    def __init__(self, config: ScannerConfig) -> None:
        self._config = config
        self._states: dict[str, SymbolState] = defaultdict(SymbolState)
        self._last_refresh_ms: int = 0

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _score(self, m: SymbolMetrics) -> float:
        w = self._config
        return (
            w.weight_oi_change * m.oi_change
            + w.weight_liq * m.liq
            + w.weight_squeeze * m.squeeze
            + w.weight_funding * m.funding
            + w.weight_spread * m.spread_bps
        )

    def _passes_gate(self, m: SymbolMetrics) -> bool:
        c = self._config
        if m.oi_usd < c.min_oi_usd:
            return False
        if m.spread_bps < c.min_spread_bps:
            return False
        if m.spread_bps > c.max_spread_bps:
            return False
        return True

    def _record_flap(self, state: SymbolState, now_ms: int) -> None:
        c = self._config
        if now_ms - state.last_flap_ms > c.flap_window_ms:
            state.flap_count = 0
        state.flap_count += 1
        state.last_flap_ms = now_ms

    def _is_flapping(self, state: SymbolState, now_ms: int) -> bool:
        c = self._config
        if now_ms - state.last_flap_ms > c.flap_window_ms:
            return False
        return state.flap_count >= c.flap_threshold

    def refresh(self, metrics_list: list[SymbolMetrics]) -> dict[str, UniverseStatus]:
        """
        Update universe from current metrics. Returns symbol -> status map.
        """
        c = self._config
        now_ms = self._now_ms()
        self._last_refresh_ms = now_ms

        # 1. Always include list -> IN_TOP5 regardless
        always = set(c.always_include)

        # 2. Filter through gate
        eligible: list[SymbolMetrics] = []
        for m in metrics_list:
            if m.symbol in always:
                eligible.append(m)
                continue
            if self._passes_gate(m):
                eligible.append(m)

        # 3. Score and sort descending
        scored = [(m, self._score(m)) for m in eligible]
        scored.sort(key=lambda x: x[1], reverse=True)

        # 4. Compute target top5 / top10 (always_include priority)
        target_top5 = set(always)
        target_top10 = set(always)

        for m, _ in scored:
            if len(target_top5) >= c.max_top:
                break
            target_top5.add(m.symbol)

        for m, _ in scored:
            if len(target_top10) >= c.max_watch:
                break
            target_top10.add(m.symbol)

        # top5 üyeleri top10'a da girer
        target_top10 |= target_top5

        # 5. Apply state transitions with hysteresis
        result: dict[str, UniverseStatus] = {}
        all_symbols = (
            set(self._states.keys())
            | {m.symbol for m in metrics_list}
            | always
        )

        for sym in all_symbols:
            state = self._states[sym]
            current = state.status

            if sym in target_top5:
                new_status = UniverseStatus.IN_TOP5
                if current != new_status:
                    self._record_flap(state, now_ms)
                state.pending_since_ms = 0
            elif sym in target_top10:
                if current == UniverseStatus.IN_TOP5:
                    # hysteresis: wait before dropping out of top5
                    if state.pending_since_ms == 0:
                        state.pending_since_ms = now_ms
                    elapsed = now_ms - state.pending_since_ms
                    if elapsed < c.hysteresis_ms or self._is_flapping(state, now_ms):
                        new_status = UniverseStatus.IN_TOP5
                    else:
                        new_status = UniverseStatus.IN_TOP10
                        self._record_flap(state, now_ms)
                elif current == UniverseStatus.OUTSIDE_PENDING:
                    new_status = UniverseStatus.IN_TOP10
                    state.pending_since_ms = 0
                else:
                    new_status = UniverseStatus.IN_TOP10
                    if current != new_status:
                        self._record_flap(state, now_ms)
            else:
                # not in top10
                if current in (UniverseStatus.IN_TOP5, UniverseStatus.IN_TOP10):
                    if state.pending_since_ms == 0:
                        state.pending_since_ms = now_ms
                    elapsed = now_ms - state.pending_since_ms
                    if elapsed < c.hysteresis_ms or self._is_flapping(state, now_ms):
                        new_status = current  # keep old
                    else:
                        new_status = UniverseStatus.OUTSIDE_PENDING
                        self._record_flap(state, now_ms)
                elif current == UniverseStatus.OUTSIDE_PENDING:
                    elapsed = now_ms - state.pending_since_ms
                    if elapsed >= c.max_pending_ms:
                        new_status = UniverseStatus.DROPPED
                    else:
                        new_status = UniverseStatus.OUTSIDE_PENDING
                else:
                    new_status = UniverseStatus.DROPPED

            state.status = new_status
            result[sym] = new_status

        return result

    def get_status(self, symbol: str) -> UniverseStatus:
        state = self._states.get(symbol)
        if state is None:
            return UniverseStatus.UNKNOWN
        return state.status

    def get_active_symbols(self) -> list[str]:
        """Symbols currently IN_TOP5 or IN_TOP10."""
        return [
            sym
            for sym, st in self._states.items()
            if st.status in (UniverseStatus.IN_TOP5, UniverseStatus.IN_TOP10)
        ]

    def get_top5(self) -> list[str]:
        return [
            sym
            for sym, st in self._states.items()
            if st.status == UniverseStatus.IN_TOP5
        ]

    def status_counts(self) -> dict:
        counts = defaultdict(int)
        for st in self._states.values():
            counts[st.status.value] += 1
        return dict(counts)