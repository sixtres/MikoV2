# src/backtest/multi_symbol_runner.py
# YAMA Y-353: DI, no global
# B2e.1 — Interleaved multi-symbol runner (DURUM §8 + §16)
#   SORU C (REVİZE): interleaved, tek event-loop, per-symbol
#     Strategy/SignalDetector, tek PositionSimulator.
#   SORU J' (determinizm): stream_multi tie-break'i bozulmaz.
#   SORU K'' (dropped): global_limit_full / per_symbol_max_position /
#     cooldown_active; (reason, symbol, ts_ms).
#   SORU X (B2e.1): Strategy/PositionSimulator.last_rejection_reason.
#   SORU F: BacktestEngine DEĞİŞMEZ; multi-symbol dispatch burada.

"""
B2e.1 — Interleaved multi-symbol runner.

Akış:
    ReplayTransport.stream_multi(symbols, ts_from, ts_to)
      -> SORU J' sırası (ts_ms, event_type_rank, symbol, source_seq)
    Her event için:
        sim.on_ohlcv(ev)    # SORU L'': exit -> funding -> MTM -> last_price
        strat.on_ohlcv(ev)  # detector + entry decision
        sim.on_entry(...)   # entry execution
    Sonunda:
        strat.finalize()    # detector flush
        sim.finalize(ts_to, {})  # END_OF_BACKTEST

Determinizm sözleşmesi: aynı girdi + aynı config -> aynı result.
Rastgelelik yoktur (FillModel bu yolda kullanılmaz).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable

from .data_quality import analyze_ohlcv_secs
from .engine import BacktestStats
from .position_sim import PositionSimConfig, PositionSimulator, Trade
from .replay_transport import (
    DepthEvent,
    OHLCVEvent,
    ReplayTransport,
    TickerEvent,
)
from .signal_detector import DetectorConfig, SignalDetector
from .strategy import Strategy, StrategyConfig

logger = logging.getLogger(__name__)

# Güvenlik üst sınırı: patolojik senaryolarda drop listesi sınırsız büyümesin.
# B2e.3'te aggregation/dedupe uygulanacak.
_DROP_HARD_CAP = 10_000


@dataclass(frozen=True, slots=True)
class DroppedEntry:
    """SORU K'' — sinyal üretildi ama pozisyon açılmadı."""
    reason: str
    symbol: str
    ts_ms: int

    def to_dict(self) -> dict:
        return {
            "reason": self.reason,
            "symbol": self.symbol,
            "ts_ms": self.ts_ms,
        }


@dataclass
class MultiSymbolResult:
    stats: BacktestStats
    trades: list[Trade]
    dropped_entries: list[DroppedEntry]
    signal_counts: dict[str, dict[str, int]]

    def to_dict(self) -> dict:
        return {
            "stats": self.stats.to_dict(),
            "trades": [t.to_dict() for t in self.trades],
            "dropped_entries": [d.to_dict() for d in self.dropped_entries],
            "signal_counts": {
                sym: dict(counts)
                for sym, counts in self.signal_counts.items()
            },
        }

# ---------------------------------------------------------------- walk-forward


@dataclass(frozen=True, slots=True)
class WalkForwardConfig:
    """
    SORU D (A): parametrik pencere ölçeği.
    SORU I.1 (B): ≥1 fold zorunlu.
    SORU I.2 (A): step_ms default = test_ms.
    SORU I.3 (A): fail-fast.
    SORU DD (B): callback_errors > 0 → fail-fast.
    """
    train_ms: int
    test_ms: int
    step_ms: int | None = None
    min_folds: int = 1
    fail_fast: bool = True

    def effective_step_ms(self) -> int:
        if self.step_ms is None or self.step_ms <= 0:
            return self.test_ms
        return self.step_ms


@dataclass(frozen=True, slots=True)
class FoldWindow:
    fold_id: int
    train_start_ms: int
    train_end_ms: int
    test_start_ms: int
    test_end_ms: int

    def to_dict(self) -> dict:
        return {
            "fold_id": self.fold_id,
            "train_start_ms": self.train_start_ms,
            "train_end_ms": self.train_end_ms,
            "test_start_ms": self.test_start_ms,
            "test_end_ms": self.test_end_ms,
        }


@dataclass
class FoldResult:
    window: FoldWindow
    trades: list[Trade]
    dropped_entries: list[DroppedEntry]
    stats: BacktestStats
    signal_counts: dict
    data_quality: dict  # {symbol: DataQualityReport.to_dict()}

    def to_dict(self) -> dict:
        return {
            "window": self.window.to_dict(),
            "trades": [t.to_dict() for t in self.trades],
            "dropped_entries": [d.to_dict() for d in self.dropped_entries],
            "stats": self.stats.to_dict(),
            "signal_counts": {
                sym: dict(c) for sym, c in self.signal_counts.items()
            },
            "data_quality": self.data_quality,
        }


@dataclass
class WalkForwardResult:
    folds: list[FoldResult]
    combined_trades: list[Trade]
    combined_dropped: list[DroppedEntry]
    fold_count: int
    single_fold_warning: bool  # SORU G′: fold_count==1 uyarısı

    def to_dict(self) -> dict:
        return {
            "fold_count": self.fold_count,
            "single_fold_warning": self.single_fold_warning,
            "folds": [f.to_dict() for f in self.folds],
            "combined_trades": [t.to_dict() for t in self.combined_trades],
            "combined_dropped": [
                d.to_dict() for d in self.combined_dropped
            ],
        }


class WalkForwardRunner:
    """
    B2e.2 — SORU D/I/M + AA/BB/CC/DD/JJ.

    Her fold:
        train_start_ms → test_end_ms aralığı TEK geçişte koşulur.
        Sadece entry_ts_ms >= test_start_ms olan trade'ler rapora girer
        (SORU M: train = warmup; SORU CC=A: warmup train son ts_ms'inde
        biter).
    Fold bağımsızlığı (BB=A + JJ=A): her fold'da MultiSymbolRunner ve
    PositionSimulator sıfırdan kurulur; train penceresi ısıtır.
    Fail-fast (SORU I.3 + DD=B): fold sonrası callback_errors > 0 →
    raise.
    """

    def __init__(
        self,
        transport: ReplayTransport,
        sim_config: PositionSimConfig,
        strategy_config: StrategyConfig,
        detector_config: DetectorConfig,
        walk_config: WalkForwardConfig,
    ) -> None:
        self._transport = transport
        self._sim_cfg = sim_config
        self._strat_cfg = strategy_config
        self._det_cfg = detector_config
        self._walk_cfg = walk_config

    # -------------------------------------------------- fold generation

    def _generate_folds(
        self, ts_from: int, ts_to: int
    ) -> list[FoldWindow]:
        cfg = self._walk_cfg
        step = cfg.effective_step_ms()
        folds: list[FoldWindow] = []
        t0 = ts_from
        while True:
            train_end = t0 + cfg.train_ms
            test_end = train_end + cfg.test_ms
            if test_end > ts_to:
                break
            folds.append(FoldWindow(
                fold_id=len(folds),
                train_start_ms=t0,
                train_end_ms=train_end,
                test_start_ms=train_end,
                test_end_ms=test_end,
            ))
            t0 += step
        return folds

    # -------------------------------------------------- data quality

    def _collect_data_quality(
        self, symbols: list[str], ts_from: int, ts_to: int
    ) -> dict:
        try:
            secs_by_symbol = self._transport.collect_ohlcv_secs(
                symbols, ts_from, ts_to
            )
        except AttributeError:
            # Test double'lar collect_ohlcv_secs sağlamıyorsa atla.
            return {}
        out: dict = {}
        for sym, secs in secs_by_symbol.items():
            rep = analyze_ohlcv_secs(sym, secs, expected_interval_sec=1)
            out[sym] = rep.to_dict()
        return out

    # -------------------------------------------------- run

    def _run_fold(
        self, fold: FoldWindow, symbols: list[str]
    ) -> FoldResult:
        sub_runner = MultiSymbolRunner(
            self._transport,
            self._sim_cfg,
            self._strat_cfg,
            self._det_cfg,
            window_id=0,
            fold_id=fold.fold_id,
        )
        raw = sub_runner.run(
            symbols, fold.train_start_ms, fold.test_end_ms,
        )

        # SORU M + CC=A: yalnızca test penceresi (test_start_ms sonrası).
        test_trades = [
            t for t in raw.trades
            if t.entry_ts_ms >= fold.test_start_ms
        ]
        test_drops = [
            d for d in raw.dropped_entries
            if d.ts_ms >= fold.test_start_ms
        ]

        # B2e.2 diagnostics: test penceresi OHLCV sec'leri.
        dq_secs: dict = {}
        for sym, secs in sub_runner._seen_ohlcv_secs.items():
            test_secs = [
                s for s in secs
                if fold.test_start_ms <= s * 1000 <= fold.test_end_ms
            ]
            dq_secs[sym] = test_secs
        data_quality: dict = {}
        for sym, secs in dq_secs.items():
            rep = analyze_ohlcv_secs(sym, secs, expected_interval_sec=1)
            data_quality[sym] = rep.to_dict()

        return FoldResult(
            window=fold,
            trades=test_trades,
            dropped_entries=test_drops,
            stats=raw.stats,
            signal_counts=raw.signal_counts,
            data_quality=data_quality,
        )

    def run(
        self, symbols: Iterable[str], ts_from: int, ts_to: int
    ) -> WalkForwardResult:
        syms = list(symbols)
        folds = self._generate_folds(ts_from, ts_to)
        if len(folds) < self._walk_cfg.min_folds:
            raise RuntimeError(
                f"walk-forward produced {len(folds)} fold(s); "
                f"min_folds={self._walk_cfg.min_folds} required "
                f"(ts_from={ts_from}, ts_to={ts_to}, "
                f"train_ms={self._walk_cfg.train_ms}, "
                f"test_ms={self._walk_cfg.test_ms})"
            )

        fold_results: list[FoldResult] = []
        for fold in folds:
            fr = self._run_fold(fold, syms)
            fold_results.append(fr)
            if self._walk_cfg.fail_fast and fr.stats.callback_errors > 0:
                raise RuntimeError(
                    f"walk-forward fail-fast: fold {fold.fold_id} "
                    f"had {fr.stats.callback_errors} callback error(s)"
                )

        combined_trades: list[Trade] = []
        combined_drops: list[DroppedEntry] = []
        for fr in fold_results:
            combined_trades.extend(fr.trades)
            combined_drops.extend(fr.dropped_entries)

        return WalkForwardResult(
            folds=fold_results,
            combined_trades=combined_trades,
            combined_dropped=combined_drops,
            fold_count=len(folds),
            single_fold_warning=(len(folds) == 1),
        )

class MultiSymbolRunner:
    """
    SORU C interleaved runner.

    BacktestEngine KULLANILMAZ — engine tek sembollü `transport.stream()`
    çağırır; multi-symbol dispatch bu sınıfta (SORU F: engine imzası
    değişmez).
    """

    def __init__(
        self,
        transport: ReplayTransport,
        sim_config: PositionSimConfig,
        strategy_config: StrategyConfig,
        detector_config: DetectorConfig,
        *,
        window_id: int = 0,
        fold_id: int = 0,
    ) -> None:
        self._transport = transport
        self._sim_config = sim_config
        self._strategy_config = strategy_config
        self._detector_config = detector_config
        self._sim = PositionSimulator(
            sim_config, window_id=window_id, fold_id=fold_id,
        )
        self._strategies: dict[str, Strategy] = {}
        self._detectors: dict[str, SignalDetector] = {}
        self._dropped: list[DroppedEntry] = []
        # B2e.2 diagnostics: fold data_quality için görülen OHLCV sec'leri.
        self._seen_ohlcv_secs: dict[str, list[int]] = {}
        # SORU K'': cooldown drop'u yalnızca blok EPİZODU başlangıcında
        # kaydedilir (1s başına spam'i engeller; per-symbol).
        self._cooldown_state: dict[str, bool] = {}

    # -------------------------------------------------- accessors

    @property
    def simulator(self) -> PositionSimulator:
        return self._sim

    @property
    def dropped_entries(self) -> list[DroppedEntry]:
        return list(self._dropped)

    @property
    def strategies(self) -> dict[str, Strategy]:
        return dict(self._strategies)

    # -------------------------------------------------- dispatch

    def _ensure_symbol(self, symbol: str) -> None:
        if symbol in self._strategies:
            return
        det = SignalDetector(self._detector_config)
        strat = Strategy(self._strategy_config, det)
        self._detectors[symbol] = det
        self._strategies[symbol] = strat

    def _record_drop(self, reason: str, symbol: str, ts_ms: int) -> None:
        if len(self._dropped) >= _DROP_HARD_CAP:
            logger.warning(
                "dropped_entries hard cap (%d) reached; "
                "symbol=%s reason=%s ts_ms=%d ignored",
                _DROP_HARD_CAP, symbol, reason, ts_ms,
            )
            return
        self._dropped.append(DroppedEntry(
            reason=reason, symbol=symbol, ts_ms=ts_ms,
        ))

    def _on_ohlcv(self, ev: OHLCVEvent) -> None:
        symbol = ev.symbol
        self._ensure_symbol(symbol)
        # B2e.2 diagnostics
        self._seen_ohlcv_secs.setdefault(symbol, []).append(ev.sec)
        # (1) SORU L'': sim candle transition + exit + funding + last_price
        self._sim.on_ohlcv(ev)
        # (2) strategy: detector + entry decision
        strat = self._strategies[symbol]
        entries = strat.on_ohlcv(ev)
        # (3) SORU K'' — cooldown_active (yalnızca yeni epizod)
        cur_reason = strat.last_rejection_reason
        is_cooldown_block = (not entries) and (
            cur_reason == "cooldown_active"
        )
        was_cooldown_block = self._cooldown_state.get(symbol, False)
        if is_cooldown_block and not was_cooldown_block:
            self._record_drop("cooldown_active", symbol, ev.ts_ms)
        self._cooldown_state[symbol] = is_cooldown_block
        # (4) entry execution → SORU K'' per_symbol / global_limit
        for entry in entries:
            ok = self._sim.on_entry(entry, symbol)
            if not ok:
                reason = self._sim.last_rejection_reason
                if reason is None:
                    # K'' dışı red (ATR hazır değil vb.) — yine de kaydedilir.
                    reason = "sim_rejected_other"
                self._record_drop(reason, symbol, ev.ts_ms)

    def _on_depth(self, ev: DepthEvent) -> None:
        # B2e.1 kapsamı: depth henüz tüketilmiyor (B2e.1S+ adayı).
        return

    def _on_ticker(self, ev: TickerEvent) -> None:
        symbol = ev.symbol
        self._ensure_symbol(symbol)
        self._strategies[symbol].on_ticker(ev)
        self._sim.on_ticker(ev)

    # -------------------------------------------------- run

    def run(
        self,
        symbols: Iterable[str],
        ts_from: int,
        ts_to: int,
    ) -> MultiSymbolResult:
        syms = list(symbols)
        stats = BacktestStats()
        stats.wall_start_ms = ts_from
        stats.wall_end_ms = ts_to
        t0 = time.monotonic()
        try:
            for ev in self._transport.stream_multi(syms, ts_from, ts_to):
                stats.events_total += 1
                if isinstance(ev, OHLCVEvent):
                    stats.ohlcv_count += 1
                    self._on_ohlcv(ev)
                elif isinstance(ev, DepthEvent):
                    stats.depth_count += 1
                    self._on_depth(ev)
                elif isinstance(ev, TickerEvent):
                    stats.ticker_count += 1
                    self._on_ticker(ev)
        finally:
            stats.wall_elapsed_s = time.monotonic() - t0

        # Sıra: tüm stratejiler flush → sim finalize
        for sym, strat in self._strategies.items():
            try:
                strat.finalize()
            except Exception as e:  # noqa: BLE001
                stats.callback_errors += 1
                stats.errors_by_type[type(e).__name__] += 1
                logger.warning(
                    "strategy.finalize error (%s): %s", sym, e,
                )

        # SORU L'' finalize: son fiyatlar sim iç state'ten okunur
        # (finalize fallback). Boş dict güvenlidir.
        self._sim.finalize(ts_to, {})

        signal_counts = {
            sym: dict(s.signal_counts)
            for sym, s in self._strategies.items()
        }
        return MultiSymbolResult(
            stats=stats,
            trades=self._sim.trades,
            dropped_entries=list(self._dropped),
            signal_counts=signal_counts,
        )