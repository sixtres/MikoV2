# tests/unit/test_backtest_multi.py
# B2e.1 — Multi-symbol runner + SORU X last_rejection_reason testleri.
# Kapsam:
#   - SORU J' tie-break (event_type_rank, symbol, source_seq)
#   - SORU X: Strategy.last_rejection_reason (cooldown_active)
#   - SORU X: PositionSimulator.last_rejection_reason
#     (per_symbol_max_position, global_limit_full)
#   - SORU K'': runner dropped_entries toplama
#   - Determinizm + per-symbol state izolasyonu

from __future__ import annotations

from src.backtest.multi_symbol_runner import MultiSymbolRunner
from src.backtest.position_sim import (
    PositionSimConfig,
    PositionSimulator,
    _Position,
)
from src.backtest.replay_transport import (
    DepthEvent,
    OHLCVEvent,
    TickerEvent,
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
    EntrySignal,
    Strategy,
    StrategyConfig,
)


# ---------------------------------------------------------- builders

def _ohlcv(symbol: str, sec: int, o: float, h: float, l: float, c: float) -> OHLCVEvent:
    return OHLCVEvent(
        sec=sec, ts_ms=sec * 1000,
        open=o, high=h, low=l, close=c,
        buy_vol=1.0, sell_vol=1.0, trade_count=1,
        symbol=symbol, source_seq=sec,
    )


def _depth(symbol: str, ts_ms: int) -> DepthEvent:
    return DepthEvent(
        ts_ms=ts_ms, version=0, bids=[], asks=[], depth=0,
        symbol=symbol, source_seq=ts_ms,
    )


def _ticker(symbol: str, ts_ms: int, funding_rate: float = 0.0) -> TickerEvent:
    return TickerEvent(
        ts_ms=ts_ms, last_price=1.0, fair_price=1.0, index_price=1.0,
        hold_vol=0.0, oi_usdt=0.0, funding_rate=funding_rate,
        next_settle_ms=0, symbol=symbol, source_seq=ts_ms,
    )


def _bars_5s(symbol: str, start_bar_sec: int, bars: list[tuple]) -> list:
    """Her (o,h,l,c) tuple'ı 5 saniyelik bar; 5 özdeş 1s event."""
    out = []
    for i, (o, h, l, c) in enumerate(bars):
        bar_sec = start_bar_sec + i * 5
        for j in range(5):
            out.append(_ohlcv(symbol, bar_sec + j, o, h, l, c))
    return out


class _FakeTransport:
    """ReplayTransport yerine test double; SQLite'a gitmez."""
    def __init__(self, events):
        self._events = list(events)

    def stream_multi(self, symbols, ts_from, ts_to):
        for ev in self._events:
            yield ev


def _detector_cfg() -> DetectorConfig:
    # Küçük lookback'ler: 20 bar içinde setup üretebilmek için.
    return DetectorConfig(
        candle_seconds=5,
        sweep_lookback=2, sweep_wick_ratio=0.5,
        mss_lookback=2,
        fvg_min_size_pct=0.0001,
        ote_low=0.62, ote_high=0.79, ote_lookback=2,
        max_history=300,
    )


def _strategy_cfg(cooldown_ms: int = 60_000, entry_window_ms: int = 300_000) -> StrategyConfig:
    return StrategyConfig(
        entry_window_ms=entry_window_ms,
        min_whale_trust=0,
        require_sweep=True,
        require_mss=True,
        require_fvg=True,
        require_ote=False,
        cooldown_ms=cooldown_ms,
    )


def _make_runner(
    events, *, max_global: int = 3, max_per_symbol: int = 1,
    cooldown_ms: int = 60_000, entry_window_ms: int = 300_000,
) -> MultiSymbolRunner:
    sim_cfg = PositionSimConfig(
        initial_equity=10_000.0, risk_pct=0.008,
        max_positions_per_symbol=max_per_symbol,
        max_positions_global=max_global,
    )
    return MultiSymbolRunner(
        _FakeTransport(events),
        sim_cfg,
        _strategy_cfg(cooldown_ms, entry_window_ms),
        _detector_cfg(),
    )


def _reversal_bars() -> list[tuple]:
    """
    15 warmup + 8 setup bar:
      bar 15..17: düşüş, low oluşturma
      bar 18    : SWEEP_DOWN + MSS_UP
      bar 19    : FVG_BULLISH
      bar 20+   : setup penceresi içinde kalır (cooldown testi)
    """
    warmup = [(100.0, 100.2, 99.8, 100.0)] * 15
    setup = [
        (99.8, 99.8, 99.5, 99.5),       # 15
        (99.5, 99.7, 99.3, 99.5),       # 16
        (99.5, 99.5, 98.0, 98.5),       # 17
        (98.3, 99.0, 97.0, 99.0),       # 18 sweep_down + mss_up
        (99.0, 100.5, 99.6, 100.3),     # 19 fvg_bullish
        (100.3, 100.5, 100.1, 100.4),   # 20
        (100.4, 100.6, 100.2, 100.5),   # 21
        (100.5, 100.7, 100.3, 100.6),   # 22
    ]
    return warmup + setup


# ---------------------------------------------------------- SORU J'

def test_j_prime_merge_key_event_type_order() -> None:
    ts = 1000
    o = OHLCVEvent(
        sec=1, ts_ms=ts, open=1.0, high=1.0, low=1.0, close=1.0,
        buy_vol=0.0, sell_vol=0.0, trade_count=0,
        symbol="BTC_USDT", source_seq=1,
    )
    d = _depth("BTC_USDT", ts)
    t = _ticker("BTC_USDT", ts)
    assert _merge_key(o) < _merge_key(d) < _merge_key(t)


def test_j_prime_merge_key_symbol_order() -> None:
    ts = 1000
    a = OHLCVEvent(
        sec=1, ts_ms=ts, open=1.0, high=1.0, low=1.0, close=1.0,
        buy_vol=0.0, sell_vol=0.0, trade_count=0,
        symbol="AAA_USDT", source_seq=1,
    )
    b = OHLCVEvent(
        sec=1, ts_ms=ts, open=1.0, high=1.0, low=1.0, close=1.0,
        buy_vol=0.0, sell_vol=0.0, trade_count=0,
        symbol="BBB_USDT", source_seq=1,
    )
    assert _merge_key(a) < _merge_key(b)


def test_j_prime_merge_key_source_seq_order() -> None:
    ts = 1000
    a = OHLCVEvent(
        sec=1, ts_ms=ts, open=1.0, high=1.0, low=1.0, close=1.0,
        buy_vol=0.0, sell_vol=0.0, trade_count=0,
        symbol="BTC_USDT", source_seq=1,
    )
    b = OHLCVEvent(
        sec=1, ts_ms=ts, open=1.0, high=1.0, low=1.0, close=1.0,
        buy_vol=0.0, sell_vol=0.0, trade_count=0,
        symbol="BTC_USDT", source_seq=2,
    )
    assert _merge_key(a) < _merge_key(b)


# ---------------------------------------------------------- SORU X — Strategy

def test_strategy_cooldown_reason_set() -> None:
    """SORU X: cooldown engellediğinde last_rejection_reason set edilir."""
    det = SignalDetector(_detector_cfg())
    strat = Strategy(_strategy_cfg(), det)
    ts0 = 1_000_000
    # Test-only: _recent'e doğrudan enjekte (detector'u çalıştırmadan
    # hizalı setup kurmak için).
    strat._recent.append(
        (ts0, Signal(kind=SignalKind.SWEEP_DOWN, ts_ms=ts0, price=100.0))
    )
    strat._recent.append(
        (ts0, Signal(kind=SignalKind.MSS_UP, ts_ms=ts0, price=100.0))
    )
    strat._recent.append(
        (ts0, Signal(kind=SignalKind.FVG_BULLISH, ts_ms=ts0, price=100.0))
    )

    out1 = strat._try_entry(ts0 + 1_000, 100.0)
    assert len(out1) == 1
    assert strat.last_rejection_reason is None

    out2 = strat._try_entry(ts0 + 2_000, 100.0)
    assert out2 == []
    assert strat.last_rejection_reason == "cooldown_active"


def test_strategy_no_reason_when_conditions_missing() -> None:
    """Setup eksikse reason None kalır (drop değil)."""
    det = SignalDetector(_detector_cfg())
    strat = Strategy(_strategy_cfg(), det)
    ts0 = 1_000_000
    strat._recent.append(
        (ts0, Signal(kind=SignalKind.SWEEP_DOWN, ts_ms=ts0, price=100.0))
    )
    out = strat._try_entry(ts0 + 1_000, 100.0)
    assert out == []
    assert strat.last_rejection_reason is None


# ---------------------------------------------------------- SORU X — PositionSimulator

def _fake_entry_signal(price: float = 100.0) -> EntrySignal:
    return EntrySignal(
        direction=Direction.LONG, ts_ms=1_000, price=price,
        reason="test", signals=(),
    )


def _fake_position(symbol: str) -> _Position:
    # Test-only: _Position doğrudan enjekte (ATR setup'ı atlamak için).
    return _Position(
        symbol=symbol, direction=Direction.LONG,
        entry_ts_ms=0, entry_bucket_sec=0,
        entry_price=100.0, qty=1.0, sl_price=95.0, tp_price=110.0,
        entry_fee=0.02,
    )


def test_sim_per_symbol_max_position_reason() -> None:
    sim = PositionSimulator(PositionSimConfig(
        max_positions_per_symbol=1, max_positions_global=5,
    ))
    sim._positions["BTC_USDT"] = _fake_position("BTC_USDT")
    ok = sim.on_entry(_fake_entry_signal(), "BTC_USDT")
    assert ok is False
    assert sim.last_rejection_reason == "per_symbol_max_position"


def test_sim_global_limit_full_reason() -> None:
    sim = PositionSimulator(PositionSimConfig(
        max_positions_per_symbol=1, max_positions_global=2,
    ))
    for sym in ("A_USDT", "B_USDT"):
        sim._positions[sym] = _fake_position(sym)
    ok = sim.on_entry(_fake_entry_signal(), "C_USDT")
    assert ok is False
    assert sim.last_rejection_reason == "global_limit_full"


# ---------------------------------------------------------- SORU K'' — Runner

def test_runner_collects_cooldown_dropped_entries() -> None:
    events = _bars_5s("BTC_USDT", 0, _reversal_bars())
    runner = _make_runner(events)
    result = runner.run(["BTC_USDT"], 0, 200_000)

    cooldown_drops = [
        d for d in result.dropped_entries if d.reason == "cooldown_active"
    ]
    assert len(cooldown_drops) >= 1
    assert all(d.symbol == "BTC_USDT" for d in cooldown_drops)
    # transition-only kayıt: tek cooldown epizodu
    assert len(cooldown_drops) == 1


def test_runner_collects_global_limit_dropped_entries() -> None:
    """İki sembol entry üretir; global=1 → ikincisi global_limit_full."""
    evs = []
    evs.extend(_bars_5s("AAA_USDT", 0, _reversal_bars()))
    evs.extend(_bars_5s("BBB_USDT", 0, _reversal_bars()))
    runner = _make_runner(evs, max_global=1, max_per_symbol=1)
    result = runner.run(["AAA_USDT", "BBB_USDT"], 0, 200_000)
    reasons = [d.reason for d in result.dropped_entries]
    assert "global_limit_full" in reasons


def test_runner_interleaved_deterministic() -> None:
    evs = []
    evs.extend(_bars_5s("AAA_USDT", 0, _reversal_bars()))
    evs.extend(_bars_5s("BBB_USDT", 0, _reversal_bars()))

    r1 = _make_runner(evs).run(["AAA_USDT", "BBB_USDT"], 0, 200_000)
    r2 = _make_runner(evs).run(["AAA_USDT", "BBB_USDT"], 0, 200_000)

    assert [t.to_dict() for t in r1.trades] == [
        t.to_dict() for t in r2.trades
    ]
    assert [d.to_dict() for d in r1.dropped_entries] == [
        d.to_dict() for d in r2.dropped_entries
    ]
    assert r1.stats.ohlcv_count == r2.stats.ohlcv_count
    assert r1.stats.events_total == r2.stats.events_total


def test_runner_per_symbol_state_isolated() -> None:
    """Farklı range'li iki sembol → farklı ATR (state karışmaz)."""
    btc = _bars_5s("BTC_USDT", 0, [(100.0, 100.5, 99.5, 100.0)] * 25)
    eth = _bars_5s("ETH_USDT", 0, [(50.0, 50.1, 49.9, 50.0)] * 25)
    runner = _make_runner(btc + eth)
    runner.run(["BTC_USDT", "ETH_USDT"], 0, 200_000)

    atr_btc = runner.simulator._atr("BTC_USDT")
    atr_eth = runner.simulator._atr("ETH_USDT")
    assert atr_btc is not None
    assert atr_eth is not None
    # BTC range 1.0, ETH range 0.2 → ATR oranı ~5
    assert atr_btc > atr_eth * 3