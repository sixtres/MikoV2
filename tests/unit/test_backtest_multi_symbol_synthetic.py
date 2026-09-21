# tests/unit/test_backtest_multi_symbol_synthetic.py
# B2e.1S — Synthetic multi-symbol validation
# SORU R 1–14 (v1) minimum alt kümesi; SORU 3 (B) sentetik-minimum kararı.
#
# B2e.1S kapsamı (8 test):
#   G1 J' determinizm end-to-end (2)
#   G4 K'' drops end-to-end — global_limit_full (1)
#   G5 MTM + finalize (2)
#   G6 Funding + cooldown (3)
#
# B2e.2S'ye ertelenen (6): G2 interleaved (2), G3 per-symbol izolasyon (3),
# ek genel determinizm (1).

from __future__ import annotations

from src.backtest.multi_symbol_runner import MultiSymbolRunner
from src.backtest.position_sim import (
    PositionSimConfig,
    PositionSimulator,
    _Position,
)
from src.backtest.replay_transport import (
    OHLCVEvent,
    _merge_key,
)
from src.backtest.signal_detector import (
    DetectorConfig,
    Signal,
    SignalDetector,
    SignalKind,
)
from src.backtest.strategy import (
    Direction,
    Strategy,
    StrategyConfig,
)


# ============================================================ builders


def _bar(symbol: str, sec: int, o: float, h: float, l: float, c: float) -> OHLCVEvent:
    return OHLCVEvent(
        sec=sec, ts_ms=sec * 1000,
        open=o, high=h, low=l, close=c,
        buy_vol=1.0, sell_vol=1.0, trade_count=1,
        symbol=symbol, source_seq=sec,
    )


def _pump(symbol: str, start_sec: int, n_bars: int,
          o: float, h: float, l: float, c: float) -> list:
    """n_bars adet 5s bar; her bar 5×1s OHLCV."""
    out = []
    for i in range(n_bars):
        base = start_sec + i * 5
        for j in range(5):
            out.append(_bar(symbol, base + j, o, h, l, c))
    return out


def _setup_bars(symbol: str, start_sec: int) -> list:
    """
    Sentetik LONG setup — sweep_down + mss_up + fvg_bullish.
    Geometri (5s bar indeksleri, detector config: sweep_lookback=2,
    mss_lookback=2, fvg_min_size_pct=0.0001):

      bar 15 (100.0, 100.1, 99.6, 99.7)   — düşüş başlangıç
      bar 16 ( 99.7,  99.8, 99.4, 99.5)   — düşüş;  prev_low=99.4
      bar 17 ( 99.5,  99.9, 98.8, 99.9)   — SWEEP_DOWN + MSS_UP
                                             (close 99.9 > 99.4 strict,
                                              wick_down/rng = 0.7/1.1 ≈ 0.64,
                                              mid = (100.1+99.4)/2 = 99.75)
      bar 18 ( 99.9, 100.5, 100.0, 100.3) — FVG_BULLISH
                                             (low 100.0 > bar16.high 99.8)
      bar 19 (100.4, 100.6, 100.3, 100.5) — ENTRY (at bar 19 start,
                                             bar 18 finalize → FVG emit)
      bar 20+ follow-up (100.4, 100.6, 100.35, 100.5) — SL/TP'ye değmez

    ENTRY anı: bar 19 ilk 1s event; _candles = bars 0..18 (19 adet),
    ATR(14) hazır; sl_distance ≈ 0.236 (floor 0.201 üstü); SL ≈ 100.28,
    TP ≈ 100.99 — follow-up bu aralıkta kalır.
    """
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


def _strategy_cfg(
    cooldown_ms: int = 60_000,
    entry_window_ms: int = 300_000,
) -> StrategyConfig:
    return StrategyConfig(
        entry_window_ms=entry_window_ms,
        min_whale_trust=0,
        require_sweep=True,
        require_mss=True,
        require_fvg=True,
        require_ote=False,
        cooldown_ms=cooldown_ms,
    )


class _FakeTransport:
    """ReplayTransport duck-type; SQLite'a gitmeden event verir."""
    def __init__(self, events):
        self._events = list(events)

    def stream_multi(self, symbols, ts_from, ts_to):
        for ev in self._events:
            yield ev


def _make_runner(
    events,
    *,
    max_global: int = 3,
    max_per_symbol: int = 1,
    cooldown_ms: int = 60_000,
    entry_window_ms: int = 300_000,
    include_funding: bool = False,
) -> MultiSymbolRunner:
    sim_cfg = PositionSimConfig(
        initial_equity=10_000.0,
        risk_pct=0.008,
        max_positions_per_symbol=max_per_symbol,
        max_positions_global=max_global,
        include_funding=include_funding,
    )
    return MultiSymbolRunner(
        _FakeTransport(events),
        sim_cfg,
        _strategy_cfg(cooldown_ms, entry_window_ms),
        _detector_cfg(),
    )


def _fake_position(symbol: str) -> _Position:
    return _Position(
        symbol=symbol,
        direction=Direction.LONG,
        entry_ts_ms=0,
        entry_bucket_sec=0,
        entry_price=100.0,
        qty=1.0,
        sl_price=95.0,
        tp_price=110.0,
        entry_fee=0.02,
    )


# ============================================================ G1 — J' determinizm


def test_s1_jprime_end_to_end_deterministic() -> None:
    """Aynı event dizisi + aynı config → birebir aynı çıktı."""
    btc = _setup_bars("BTC_USDT", 0)
    eth = _setup_bars("ETH_USDT", 0)
    events = sorted(btc + eth, key=_merge_key)

    r1 = _make_runner(events).run(["BTC_USDT", "ETH_USDT"], 0, 300_000)
    r2 = _make_runner(events).run(["BTC_USDT", "ETH_USDT"], 0, 300_000)

    s1 = r1.stats.to_dict()
    s2 = r2.stats.to_dict()
    s1.pop("wall_elapsed_s", None)
    s2.pop("wall_elapsed_s", None)
    assert s1 == s2
    assert [t.to_dict() for t in r1.trades] == [t.to_dict() for t in r2.trades]
    assert [d.to_dict() for d in r1.dropped_entries] == [
        d.to_dict() for d in r2.dropped_entries
    ]


def test_s1_jprime_stats_counts() -> None:
    """J' sırasına konmuş event'ler tam sayılır."""
    btc = _setup_bars("BTC_USDT", 0)
    eth = _setup_bars("ETH_USDT", 0)
    events = sorted(btc + eth, key=_merge_key)

    runner = _make_runner(events)
    result = runner.run(["BTC_USDT", "ETH_USDT"], 0, 300_000)

    assert result.stats.events_total == len(events)
    assert result.stats.ohlcv_count == len(events)


# ============================================================ G4 — K'' drops


def test_s2_global_limit_drop_end_to_end() -> None:
    """İki sembol aynı anda setup üretir; global=1 → ikinci drop."""
    btc = _setup_bars("BTC_USDT", 0)
    eth = _setup_bars("ETH_USDT", 0)
    events = sorted(btc + eth, key=_merge_key)

    runner = _make_runner(events, max_global=1, max_per_symbol=1)
    result = runner.run(["BTC_USDT", "ETH_USDT"], 0, 300_000)

    reasons = [d.reason for d in result.dropped_entries]
    assert "global_limit_full" in reasons
    # Drop'un hangi sembole ait olduğu izlenebilir olmalı
    global_drops = [
        d for d in result.dropped_entries if d.reason == "global_limit_full"
    ]
    assert all(d.symbol in {"BTC_USDT", "ETH_USDT"} for d in global_drops)


# ============================================================ G5 — MTM + finalize


def test_s3_mtm_equity_reflects_unrealized() -> None:
    """Açık pozisyon varken equity = realized + unrealized."""
    sim = PositionSimulator(PositionSimConfig())
    sim._positions["BTC_USDT"] = _fake_position("BTC_USDT")
    sim._last_price["BTC_USDT"] = 105.0

    # realized = 10000; unrealized = (105 - 100) * 1 = +5
    assert abs(sim.equity - 10_005.0) < 1e-9


def test_s3_finalize_creates_end_of_backtest_trade() -> None:
    """finalize, açık pozisyonu END_OF_BACKTEST ile kapatır."""
    sim = PositionSimulator(PositionSimConfig())
    sim._positions["BTC_USDT"] = _fake_position("BTC_USDT")
    sim._last_price["BTC_USDT"] = 102.0

    sim.finalize(last_ts_ms=1_000_000, last_prices={})

    trades = sim.trades
    assert len(trades) == 1
    assert trades[0].symbol == "BTC_USDT"
    assert trades[0].exit_reason.value == "END_OF_BACKTEST"
    # sim state'i tükendi
    assert sim.open_positions == {}


# ============================================================ G6 — Funding + cooldown


def test_s4_funding_applied_to_open_position() -> None:
    """include_funding=True; 08:00 UTC sınırı geçilince funding_paid set."""
    sim = PositionSimulator(PositionSimConfig(
        include_funding=True,
        max_positions_global=5,
    ))
    sim._positions["BTC_USDT"] = _fake_position("BTC_USDT")
    sim._last_funding_rate["BTC_USDT"] = 0.0001
    sim._last_price["BTC_USDT"] = 100.0

    # 08:00 UTC sonrası ilk OHLCV; boundary'yi geçtiği için funding tetiklenir
    ts_ms = 8 * 3600 * 1000 + 1_000
    sim._next_funding_ms["BTC_USDT"] = 8 * 3600 * 1000
    ev = _bar("BTC_USDT", ts_ms // 1000, 100.0, 100.0, 100.0, 100.0)
    sim.on_ohlcv(ev)

    assert sim._positions["BTC_USDT"].funding_paid != 0.0


def test_s4_cooldown_reason_set_by_strategy() -> None:
    """Setup var, cooldown engelliyor → last_rejection_reason set."""
    det = SignalDetector(_detector_cfg())
    strat = Strategy(_strategy_cfg(cooldown_ms=60_000), det)
    ts0 = 1_000_000
    strat._recent.append((ts0, Signal(SignalKind.SWEEP_DOWN, ts0, 100.0)))
    strat._recent.append((ts0, Signal(SignalKind.MSS_UP, ts0, 100.0)))
    strat._recent.append((ts0, Signal(SignalKind.FVG_BULLISH, ts0, 100.0)))

    out1 = strat._try_entry(ts0 + 1_000, 100.0)
    assert len(out1) == 1
    assert strat.last_rejection_reason is None

    out2 = strat._try_entry(ts0 + 2_000, 100.0)
    assert out2 == []
    assert strat.last_rejection_reason == "cooldown_active"


def test_s4_cooldown_single_episode_drop_in_runner() -> None:
    """Cooldown epizodu boyunca drop listesinde tek kayıt (spam engeli)."""
    evs = _setup_bars("BTC_USDT", 0)
    runner = _make_runner(evs, cooldown_ms=60_000, entry_window_ms=300_000)
    result = runner.run(["BTC_USDT"], 0, 300_000)

    cooldown_drops = [
        d for d in result.dropped_entries if d.reason == "cooldown_active"
    ]
    # En fazla 1 epizod kaydı (SORU K'' transition-only)
    assert len(cooldown_drops) <= 1
    if cooldown_drops:
        assert cooldown_drops[0].symbol == "BTC_USDT"