# tests/unit/test_backtest_walkforward.py
# B2e.2 — Walk-forward runner testleri.
# Kararlar: SORU D/I/M + AA/BB/CC/DD/EE/FF/JJ.

from __future__ import annotations

import pytest

from src.backtest.multi_symbol_runner import (
    MultiSymbolRunner,
    WalkForwardConfig,
    WalkForwardRunner,
)
from src.backtest.position_sim import PositionSimConfig
from src.backtest.replay_transport import OHLCVEvent, _merge_key
from src.backtest.signal_detector import DetectorConfig
from src.backtest.strategy import StrategyConfig


# ============================================================ helpers


def _bar(symbol: str, sec: int, o: float, h: float, l: float, c: float) -> OHLCVEvent:
    return OHLCVEvent(
        sec=sec, ts_ms=sec * 1000,
        open=o, high=h, low=l, close=c,
        buy_vol=1.0, sell_vol=1.0, trade_count=1,
        symbol=symbol, source_seq=sec,
    )


def _pump(symbol: str, start_sec: int, n_bars: int,
          o: float, h: float, l: float, c: float) -> list:
    out = []
    for i in range(n_bars):
        base = start_sec + i * 5
        for j in range(5):
            out.append(_bar(symbol, base + j, o, h, l, c))
    return out


def _setup_bars(symbol: str, start_sec: int) -> list:
    """LONG setup — sweep_down + mss_up + fvg_bullish (B2e.1S ile aynı)."""
    out: list = []
    out.extend(_pump(symbol, start_sec, 15, 100.0, 100.2, 99.8, 100.0))
    out.extend(_pump(symbol, start_sec + 75, 1, 100.0, 100.1, 99.6, 99.7))
    out.extend(_pump(symbol, start_sec + 80, 1, 99.7, 99.8, 99.4, 99.5))
    out.extend(_pump(symbol, start_sec + 85, 1, 99.5, 99.9, 98.8, 99.9))
    out.extend(_pump(symbol, start_sec + 90, 1, 99.9, 100.5, 100.0, 100.3))
    out.extend(_pump(symbol, start_sec + 95, 1, 100.4, 100.6, 100.3, 100.5))
    out.extend(_pump(symbol, start_sec + 100, 5, 100.4, 100.6, 100.35, 100.5))
    return out


def _detector_cfg() -> DetectorConfig:
    return DetectorConfig(
        candle_seconds=5,
        sweep_lookback=2, sweep_wick_ratio=0.5,
        mss_lookback=2,
        fvg_min_size_pct=0.0001,
        ote_low=0.62, ote_high=0.79, ote_lookback=2,
        max_history=300,
    )


def _strategy_cfg() -> StrategyConfig:
    return StrategyConfig(
        entry_window_ms=300_000,
        min_whale_trust=0,
        require_sweep=True, require_mss=True, require_fvg=True,
        require_ote=False,
        cooldown_ms=60_000,
    )


class _FakeTransport:
    """ReplayTransport duck-type; ts filtresi uygular."""
    def __init__(self, events):
        self._events = list(events)

    def stream_multi(self, symbols, ts_from, ts_to):
        for ev in self._events:
            if ts_from <= ev.ts_ms <= ts_to:
                yield ev

    def collect_ohlcv_secs(self, symbols, ts_from, ts_to):
        out: dict = {s: [] for s in symbols}
        for ev in self._events:
            if isinstance(ev, OHLCVEvent) and ev.symbol in out:
                if ts_from <= ev.ts_ms <= ts_to:
                    out[ev.symbol].append(ev.sec)
        for s in out:
            out[s].sort()
        return out


def _make_walk_runner(events, walk_cfg):
    return WalkForwardRunner(
        _FakeTransport(events),
        PositionSimConfig(initial_equity=10_000.0, risk_pct=0.008),
        _strategy_cfg(),
        _detector_cfg(),
        walk_cfg,
    )


# ============================================================ fold üretimi


def test_wf_config_step_default_is_test_ms() -> None:
    cfg = WalkForwardConfig(train_ms=20_000, test_ms=10_000)
    assert cfg.effective_step_ms() == 10_000


def test_wf_config_step_explicit() -> None:
    cfg = WalkForwardConfig(train_ms=20_000, test_ms=10_000, step_ms=5_000)
    assert cfg.effective_step_ms() == 5_000


def test_wf_fold_generation_basic() -> None:
    cfg = WalkForwardConfig(train_ms=20_000, test_ms=20_000)
    runner = _make_walk_runner([], cfg)
    folds = runner._generate_folds(0, 100_000)
    # 4 fold: (0-20k,20-40k), (20-40k,40-60k), (40-60k,60-80k), (60-80k,80-100k)
    assert len(folds) == 4
    assert folds[0].fold_id == 0
    assert folds[0].train_start_ms == 0
    assert folds[0].test_start_ms == 20_000
    assert folds[0].test_end_ms == 40_000
    assert folds[3].test_end_ms == 100_000


def test_wf_fold_generation_too_small_raises_min_folds() -> None:
    # train+test=100_000 > ts_to=90_000 → 0 fold → min_folds raise.
    cfg = WalkForwardConfig(train_ms=50_000, test_ms=50_000)
    runner = _make_walk_runner([], cfg)
    with pytest.raises(RuntimeError, match="min_folds"):
        runner.run(["BTC_USDT"], 0, 90_000)


# ============================================================ run


def test_wf_runner_produces_folds_with_test_trades() -> None:
    # ts_to=110_000: train=50k, test=60k → t0=0 fold 0; t0+=step(200k)
    # → 200k+60k > 110k → dur. Tek fold.
    events = _setup_bars("BTC_USDT", 0)
    walk_cfg = WalkForwardConfig(
        train_ms=50_000, test_ms=60_000, step_ms=200_000,
    )
    runner = _make_walk_runner(events, walk_cfg)
    result = runner.run(["BTC_USDT"], 0, 110_000)
    assert result.fold_count == 1
    assert result.single_fold_warning is True


def test_wf_trades_carry_fold_id() -> None:
    events = _setup_bars("BTC_USDT", 0) + _setup_bars("BTC_USDT", 200)
    walk_cfg = WalkForwardConfig(
        train_ms=50_000, test_ms=60_000, step_ms=200_000,
    )
    runner = _make_walk_runner(events, walk_cfg)
    result = runner.run(["BTC_USDT"], 0, 500_000)
    for fold in result.folds:
        for t in fold.trades:
            assert t.fold_id == fold.window.fold_id


def test_wf_combined_trades_are_test_only() -> None:
    """Train penceresinde üretilen trade'ler combined'a girmez."""
    events = _setup_bars("BTC_USDT", 0) + _setup_bars("BTC_USDT", 200)
    walk_cfg = WalkForwardConfig(
        train_ms=50_000, test_ms=60_000, step_ms=200_000,
    )
    runner = _make_walk_runner(events, walk_cfg)
    result = runner.run(["BTC_USDT"], 0, 500_000)
    for t in result.combined_trades:
        fold = next(
            f for f in result.folds if f.window.fold_id == t.fold_id
        )
        assert t.entry_ts_ms >= fold.window.test_start_ms


def test_wf_data_quality_present_per_fold() -> None:
    events = _setup_bars("BTC_USDT", 0)
    walk_cfg = WalkForwardConfig(
        train_ms=50_000, test_ms=60_000, step_ms=200_000,
    )
    runner = _make_walk_runner(events, walk_cfg)
    result = runner.run(["BTC_USDT"], 0, 110_000)
    assert result.fold_count == 1
    dq = result.folds[0].data_quality
    assert "BTC_USDT" in dq
    assert "completeness" in dq["BTC_USDT"]
    assert "max_gap_sec" in dq["BTC_USDT"]


def test_wf_fail_fast_on_callback_error(monkeypatch) -> None:
    """SORU DD=B: callback_errors > 0 → fail_fast raise."""
    from src.backtest import strategy as strat_mod

    def broken_finalize(self):
        raise RuntimeError("simulated finalize error")

    monkeypatch.setattr(strat_mod.Strategy, "finalize", broken_finalize)

    events = _setup_bars("BTC_USDT", 0)
    walk_cfg = WalkForwardConfig(
        train_ms=50_000, test_ms=60_000, step_ms=200_000,
        fail_fast=True,
    )
    runner = _make_walk_runner(events, walk_cfg)
    with pytest.raises(RuntimeError, match="fail-fast"):
        runner.run(["BTC_USDT"], 0, 500_000)


def test_wf_fail_fast_disabled_does_not_raise(monkeypatch) -> None:
    from src.backtest import strategy as strat_mod

    def broken_finalize(self):
        raise RuntimeError("simulated finalize error")

    monkeypatch.setattr(strat_mod.Strategy, "finalize", broken_finalize)

    events = _setup_bars("BTC_USDT", 0)
    walk_cfg = WalkForwardConfig(
        train_ms=50_000, test_ms=60_000, step_ms=200_000,
        fail_fast=False,
    )
    runner = _make_walk_runner(events, walk_cfg)
    result = runner.run(["BTC_USDT"], 0, 110_000)
    assert result.fold_count == 1
    assert result.folds[0].stats.callback_errors > 0


# ============================================================ determinizm


def test_wf_deterministic() -> None:
    events = _setup_bars("BTC_USDT", 0) + _setup_bars("BTC_USDT", 200)
    walk_cfg = WalkForwardConfig(
        train_ms=50_000, test_ms=60_000, step_ms=200_000,
    )
    r1 = _make_walk_runner(events, walk_cfg).run(["BTC_USDT"], 0, 500_000)
    r2 = _make_walk_runner(events, walk_cfg).run(["BTC_USDT"], 0, 500_000)

    s1 = [f.stats.to_dict() for f in r1.folds]
    s2 = [f.stats.to_dict() for f in r2.folds]
    for d in s1 + s2:
        d.pop("wall_elapsed_s", None)
    assert s1 == s2
    assert [t.to_dict() for t in r1.combined_trades] == [
        t.to_dict() for t in r2.combined_trades
    ]


# ============================================================ B2e.2S sentetik
# SORU LL (A) + A1 (A): 4 fold-aritmetiği senaryosu.


def _bars_with_gap(
    symbol: str,
    start_sec: int,
    pre_bars: int,
    gap_sec: int,
    post_bars: int,
) -> list:
    """pre_bars 5s bar + gap_sec saniyelik boşluk + post_bars 5s bar."""
    out: list = []
    for i in range(pre_bars):
        base = start_sec + i * 5
        for j in range(5):
            out.append(_bar(symbol, base + j, 100.0, 100.2, 99.8, 100.0))
    base_after = start_sec + pre_bars * 5 + gap_sec
    for i in range(post_bars):
        base = base_after + i * 5
        for j in range(5):
            out.append(_bar(symbol, base + j, 100.0, 100.2, 99.8, 100.0))
    return out


def test_wf_synthetic_step_greater_than_test() -> None:
    """
    LL senaryo 1: step > test_ms → ardışık test pencereleri arasında
    boşluk oluşur (örtüşme yok).
    """
    cfg = WalkForwardConfig(
        train_ms=20_000, test_ms=10_000, step_ms=30_000,
    )
    runner = _make_walk_runner([], cfg)
    folds = runner._generate_folds(0, 90_000)
    assert len(folds) == 3
    # fold0 test [20k,30k); fold1 test [50k,60k) → 20k boşluk
    assert folds[1].test_start_ms - folds[0].test_end_ms == 20_000
    # fold1 test [50k,60k); fold2 test [80k,90k) → 20k boşluk
    assert folds[2].test_start_ms - folds[1].test_end_ms == 20_000


def test_wf_synthetic_step_nonpositive_defaults_to_test() -> None:
    """
    LL senaryo 2 + SORU A1=A: step_ms None veya ≤0 → test_ms default
    (SORU I.2=A). Fail-fast DEĞİL.
    """
    cfg = WalkForwardConfig(train_ms=10_000, test_ms=5_000, step_ms=0)
    assert cfg.effective_step_ms() == 5_000
    cfg = WalkForwardConfig(train_ms=10_000, test_ms=5_000, step_ms=-1_000)
    assert cfg.effective_step_ms() == 5_000
    cfg = WalkForwardConfig(train_ms=10_000, test_ms=5_000)
    assert cfg.effective_step_ms() == 5_000


def test_wf_synthetic_multi_fold_deterministic() -> None:
    """
    LL senaryo 3: çok fold'lu koşuda determinizm — aynı girdi, aynı
    çıktı. train=20k, test=20k, step=20k, ts_to=200k → 9 fold.
    """
    events = _setup_bars("BTC_USDT", 0)
    walk_cfg = WalkForwardConfig(
        train_ms=20_000, test_ms=20_000, step_ms=20_000,
    )
    runner = _make_walk_runner(events, walk_cfg)
    r1 = runner.run(["BTC_USDT"], 0, 200_000)
    r2 = runner.run(["BTC_USDT"], 0, 200_000)

    assert r1.fold_count == 9
    assert r1.fold_count == r2.fold_count
    assert [f.window.to_dict() for f in r1.folds] == [
        f.window.to_dict() for f in r2.folds
    ]

    s1 = [f.stats.to_dict() for f in r1.folds]
    s2 = [f.stats.to_dict() for f in r2.folds]
    for d in s1 + s2:
        d.pop("wall_elapsed_s", None)
    assert s1 == s2

    assert [t.to_dict() for t in r1.combined_trades] == [
        t.to_dict() for t in r2.combined_trades
    ]


def test_wf_synthetic_boundary_gap_detected() -> None:
    """
    LL senaryo 4: fold test penceresi içindeki veri boşluğu
    data_quality raporuna gap olarak yansır.

    Fold: train [0,10k), test [10k,70k) ms = sec [10,70).
    Event'ler: sec 10..19 (pre) + sec 50..69 (post) → sec 20..49 boşluk.
    Beklenen: gap_count=1, max_gap_sec=31 (50-19).
    """
    events = _bars_with_gap(
        "BTC_USDT", start_sec=10, pre_bars=2, gap_sec=30, post_bars=4,
    )
    walk_cfg = WalkForwardConfig(
        train_ms=10_000, test_ms=60_000, step_ms=200_000,
    )
    runner = _make_walk_runner(events, walk_cfg)
    result = runner.run(["BTC_USDT"], 0, 80_000)

    assert result.fold_count == 1
    dq = result.folds[0].data_quality["BTC_USDT"]
    assert dq["gap_count"] == 1
    assert dq["max_gap_sec"] == 31
    assert dq["sample_count"] == 30