# tests/unit/test_position_sim.py
# B2c — Position simulator tests (DURUM §8, 13 test)

from __future__ import annotations

from src.backtest.position_sim import (
    ExitReason,
    PositionSimConfig,
    PositionSimulator,
)
from src.backtest.replay_transport import OHLCVEvent, TickerEvent
from src.backtest.strategy import Direction, EntrySignal


def _ohlcv(sec, o, h, l, c, symbol="BTC_USDT"):
    return OHLCVEvent(
        sec=sec, ts_ms=sec * 1000,
        open=o, high=h, low=l, close=c,
        buy_vol=0.0, sell_vol=0.0, trade_count=1,
        symbol=symbol,
    )


def _entry(direction, ts_ms, price):
    return EntrySignal(
        direction=direction, ts_ms=ts_ms, price=price,
        reason="test", signals=(),
    )


def _warm(sim, start_sec, n, price=100.0, half_range=0.5,
          symbol="BTC_USDT"):
    """Feed n 5s candles with stable OHLC for ATR history."""
    sec = start_sec
    last_sec = sec
    for _ in range(n):
        sim.on_ohlcv(_ohlcv(
            sec, price, price + half_range, price - half_range, price,
            symbol=symbol,
        ))
        last_sec = sec
        sec += 5
    return last_sec


# ------------------------------------------------------------- 1
def test_no_entry_no_trades():
    sim = PositionSimulator(PositionSimConfig())
    _warm(sim, 1000, 25)
    assert sim.trades == []
    assert sim.equity == sim._cfg.initial_equity


# ------------------------------------------------------------- 2
def test_long_entry_tp_hit():
    sim = PositionSimulator(PositionSimConfig())
    last_sec = _warm(sim, 1000, 25, price=100.0, half_range=0.5)
    entry_ts = (last_sec + 5) * 1000
    assert sim.on_entry(_entry(Direction.LONG, entry_ts, 100.0), "BTC_USDT")
    # next candle hits TP (entry_bucket atlanır; sonraki bucket kontrol edilir)
    sim.on_ohlcv(_ohlcv(last_sec + 10, 100.0, 100.3, 99.9, 100.0))
    sim.on_ohlcv(_ohlcv(last_sec + 15, 100.0, 102.0, 100.0, 101.5))
    sim.on_ohlcv(_ohlcv(last_sec + 20, 101.5, 101.6, 101.4, 101.5))
    assert len(sim.trades) == 1
    t = sim.trades[0]
    assert t.direction == Direction.LONG
    assert t.exit_reason == ExitReason.TP
    assert t.r_multiple > 1.9


# ------------------------------------------------------------- 3
def test_long_entry_sl_hit():
    sim = PositionSimulator(PositionSimConfig())
    last_sec = _warm(sim, 1000, 25, price=100.0, half_range=0.5)
    entry_ts = (last_sec + 5) * 1000
    assert sim.on_entry(_entry(Direction.LONG, entry_ts, 100.0), "BTC_USDT")
    sim.on_ohlcv(_ohlcv(last_sec + 10, 100.0, 100.3, 99.9, 100.0))
    sim.on_ohlcv(_ohlcv(last_sec + 15, 100.0, 100.1, 98.0, 99.0))
    sim.on_ohlcv(_ohlcv(last_sec + 20, 99.0, 99.1, 98.9, 99.0))
    assert len(sim.trades) == 1
    t = sim.trades[0]
    assert t.direction == Direction.LONG
    assert t.exit_reason == ExitReason.SL
    assert t.r_multiple < -0.9


# ------------------------------------------------------------- 4
def test_short_entry_tp_hit():
    sim = PositionSimulator(PositionSimConfig())
    last_sec = _warm(sim, 1000, 25, price=100.0, half_range=0.5)
    entry_ts = (last_sec + 5) * 1000
    assert sim.on_entry(_entry(Direction.SHORT, entry_ts, 100.0), "BTC_USDT")
    sim.on_ohlcv(_ohlcv(last_sec + 10, 100.0, 100.1, 99.7, 100.0))
    sim.on_ohlcv(_ohlcv(last_sec + 15, 100.0, 100.0, 98.0, 98.5))
    sim.on_ohlcv(_ohlcv(last_sec + 20, 98.5, 98.6, 98.4, 98.5))
    assert len(sim.trades) == 1
    t = sim.trades[0]
    assert t.direction == Direction.SHORT
    assert t.exit_reason == ExitReason.TP
    assert t.r_multiple > 1.9


# ------------------------------------------------------------- 5
def test_short_entry_sl_hit():
    sim = PositionSimulator(PositionSimConfig())
    last_sec = _warm(sim, 1000, 25, price=100.0, half_range=0.5)
    entry_ts = (last_sec + 5) * 1000
    assert sim.on_entry(_entry(Direction.SHORT, entry_ts, 100.0), "BTC_USDT")
    sim.on_ohlcv(_ohlcv(last_sec + 10, 100.0, 100.1, 99.7, 100.0))
    sim.on_ohlcv(_ohlcv(last_sec + 15, 100.0, 102.0, 99.9, 101.0))
    sim.on_ohlcv(_ohlcv(last_sec + 20, 101.0, 101.1, 100.9, 101.0))
    assert len(sim.trades) == 1
    t = sim.trades[0]
    assert t.direction == Direction.SHORT
    assert t.exit_reason == ExitReason.SL
    assert t.r_multiple < -0.9


# ------------------------------------------------------------- 6
def test_same_candle_sl_first_long():
    """SORU D: aynı 5s mumda TP ve SL ikisi de tetiklenirse → SL (konservatif)."""
    sim = PositionSimulator(PositionSimConfig())
    last_sec = _warm(sim, 1000, 25, price=100.0, half_range=0.5)
    entry_ts = (last_sec + 5) * 1000
    assert sim.on_entry(_entry(Direction.LONG, entry_ts, 100.0), "BTC_USDT")
    sim.on_ohlcv(_ohlcv(last_sec + 10, 100.0, 100.1, 99.9, 100.0))
    # Both hit: high >= TP (101.25), low <= SL (99.75)
    sim.on_ohlcv(_ohlcv(last_sec + 15, 100.0, 102.0, 98.0, 100.0))
    sim.on_ohlcv(_ohlcv(last_sec + 20, 100.0, 100.1, 99.9, 100.0))
    assert len(sim.trades) == 1
    assert sim.trades[0].exit_reason == ExitReason.SL


# ------------------------------------------------------------- 7
def test_per_symbol_max_one_position():
    sim = PositionSimulator(PositionSimConfig(max_positions_global=10))
    last_sec = _warm(sim, 1000, 25)
    ts = (last_sec + 5) * 1000
    assert sim.on_entry(_entry(Direction.LONG, ts, 100.0), "BTC_USDT") is True
    assert sim.on_entry(_entry(Direction.LONG, ts, 100.0), "BTC_USDT") is False


# ------------------------------------------------------------- 8
def test_global_concurrent_limit():
    sim = PositionSimulator(PositionSimConfig(max_positions_global=2))
    last_sec = _warm(sim, 1000, 25, symbol="BTC_USDT")
    _warm(sim, 1000, 25, symbol="ETH_USDT")
    _warm(sim, 1000, 25, symbol="SOL_USDT")
    ts = (last_sec + 5) * 1000
    assert sim.on_entry(_entry(Direction.LONG, ts, 100.0), "BTC_USDT")
    assert sim.on_entry(_entry(Direction.SHORT, ts, 100.0), "ETH_USDT")
    assert sim.on_entry(_entry(Direction.LONG, ts, 100.0), "SOL_USDT") is False


# ------------------------------------------------------------- 9
def test_max_sl_distance_cap():
    """ATR çok büyükse SL 0.025*entry ile sınırlanır."""
    sim = PositionSimulator(PositionSimConfig())
    # ATR ~ 10 (half_range 5 → H-L = 10)
    _warm(sim, 1000, 25, price=100.0, half_range=5.0)
    ts = 1000 + 25 * 5
    ts_ms = ts * 1000
    assert sim.on_entry(_entry(Direction.LONG, ts_ms, 100.0), "BTC_USDT")
    pos = sim.open_positions["BTC_USDT"]
    # sl distance should be capped at 0.025*entry ~ 2.5 (slip sonrası)
    assert abs(pos.entry_price - pos.sl_price) < 3.0


# ------------------------------------------------------------- 10
def test_atr_warmup_rejects_entry():
    sim = PositionSimulator(PositionSimConfig(atr_period=14))
    _warm(sim, 1000, 5)  # sadece 4 tamamlanmış mum
    ts_ms = (1000 + 5 * 5) * 1000
    assert sim.on_entry(_entry(Direction.LONG, ts_ms, 100.0), "BTC_USDT") is False


# ------------------------------------------------------------- 11
def test_position_sizing_formula():
    cfg = PositionSimConfig(initial_equity=10_000.0, risk_pct=0.008)
    sim = PositionSimulator(cfg)
    last_sec = _warm(sim, 1000, 25, price=100.0, half_range=0.5)
    ts_ms = (last_sec + 5) * 1000
    sim.on_entry(_entry(Direction.LONG, ts_ms, 100.0), "BTC_USDT")
    pos = sim.open_positions["BTC_USDT"]
    sl_dist = abs(pos.entry_price - pos.sl_price)
    expected_qty = (cfg.initial_equity * cfg.risk_pct) / sl_dist
    assert abs(pos.qty - expected_qty) < 1e-6


# ------------------------------------------------------------- 12
def test_funding_accrual():
    cfg = PositionSimConfig(include_funding=True, fee_taker=0.0, fee_maker=0.0)
    sim = PositionSimulator(cfg)
    # warmup near 7:56 (28680 s → 7:58)
    last_sec = _warm(sim, 28680, 20, price=100.0, half_range=0.5)
    ts_ms = (last_sec + 5) * 1000
    assert sim.on_entry(_entry(Direction.LONG, ts_ms, 100.0), "BTC_USDT")
    sim.on_ticker(TickerEvent(
        ts_ms=ts_ms, last_price=100.0, fair_price=100.0,
        index_price=100.0, hold_vol=0.0, oi_usdt=1_000_000.0,
        funding_rate=0.0001, next_settle_ms=0,
    ))
    # 8h UTC boundary: 28800 s. Feed across.
    # SL=99.75, TP=101.25 → dar aralık seçilir ki SL/TP tetiklenmesin.
    for s in (last_sec + 10, last_sec + 15, last_sec + 20,
              last_sec + 25, last_sec + 30):
        sim.on_ohlcv(_ohlcv(s, 100.0, 100.1, 100.0, 100.0))
    assert len(sim.trades) == 0  # pozisyon hâlâ açık
    pos = sim.open_positions["BTC_USDT"]
    assert pos.funding_paid > 0.0


# ------------------------------------------------------------- 13
def test_report_fields_and_r_multiple():
    cfg = PositionSimConfig(include_funding=False)
    sim = PositionSimulator(cfg)
    last_sec = _warm(sim, 1000, 25, price=100.0, half_range=0.5)
    ts_ms = (last_sec + 5) * 1000
    sim.on_entry(_entry(Direction.LONG, ts_ms, 100.0), "BTC_USDT")
    sim.on_ohlcv(_ohlcv(last_sec + 10, 100.0, 100.3, 99.9, 100.0))
    sim.on_ohlcv(_ohlcv(last_sec + 15, 100.0, 102.0, 100.0, 101.5))
    sim.on_ohlcv(_ohlcv(last_sec + 20, 101.5, 101.6, 101.4, 101.5))
    rpt = sim.build_report()
    d = rpt.to_dict()
    assert d["total_trades"] == 1
    assert d["win_rate"] == 1.0
    assert d["avg_r_multiple"] > 1.9
    assert d["final_equity"] > d["initial_equity"]
    assert d["total_return_pct"] > 0.0
    assert d["max_drawdown_pct"] >= 0.0


# ------------------------------------------------------------- 14
def test_min_sl_distance_floor_applied():
    """ATR çok küçük olsa bile SL min_sl_distance_pct'in altına inmez (SORU G-C)."""
    cfg = PositionSimConfig(min_sl_distance_pct=0.002)
    sim = PositionSimulator(cfg)
    # half_range=0.01 → ATR≈0.02 → sl_raw=0.01; signal_close=100 → floor=0.2
    _warm(sim, 1000, 25, price=100.0, half_range=0.01)
    ts_ms = (1000 + 25 * 5) * 1000
    assert sim.on_entry(_entry(Direction.LONG, ts_ms, 100.0), "BTC_USDT")
    pos = sim.open_positions["BTC_USDT"]
    sl_dist = abs(pos.entry_price - pos.sl_price)
    assert sl_dist >= 0.2 - 1e-6


# ------------------------------------------------------------- 15
def test_entry_slippage_bps_applied():
    """2 bps LONG → entry_fill = signal_close × (1 + 0.0002) (SORU H-A)."""
    cfg = PositionSimConfig(entry_slippage_bps=2.0)
    sim = PositionSimulator(cfg)
    _warm(sim, 1000, 25, price=100.0, half_range=0.5)
    ts_ms = (1000 + 25 * 5) * 1000
    sim.on_entry(_entry(Direction.LONG, ts_ms, 100.0), "BTC_USDT")
    pos = sim.open_positions["BTC_USDT"]
    assert abs(pos.entry_price - 100.02) < 1e-6


# ------------------------------------------------------------- 16
def test_entry_slippage_bps_applied_short():
    """2 bps SHORT → entry_fill = signal_close × (1 - 0.0002) (SORU H-A)."""
    cfg = PositionSimConfig(entry_slippage_bps=2.0)
    sim = PositionSimulator(cfg)
    _warm(sim, 1000, 25, price=100.0, half_range=0.5)
    ts_ms = (1000 + 25 * 5) * 1000
    sim.on_entry(_entry(Direction.SHORT, ts_ms, 100.0), "BTC_USDT")
    pos = sim.open_positions["BTC_USDT"]
    assert abs(pos.entry_price - 99.98) < 1e-6