# src/backtest/position_sim.py
# YAMA Y-353: DI, no global
# REV8: B2c — Position simulator + PnL (DURUM §8)

"""
B2c — Position simulator.

Consumes EntrySignal from Strategy, tracks per-symbol positions
(max 1 concurrent) + global concurrency, applies TP/SL exits on 5s
OHLCV high/low, optional funding cost accrual, produces Trade list
and summary report.

Kilitli kararlar (DURUM §8):
  SORU A: SL = entry ∓ 0.5×ATR(14, 5s); TP = entry ± 2R
          + max_sl_distance_pct 0.025 üst sınır
  SORU B: qty = (equity × risk_pct) / |entry − SL|
          PROD=0.006 / TEST=0.008 (AnaYasa §3)
  SORU C: entry = signal bar close ± leverage-adjusted slippage
  SORU D: aynı 5s mumda TP+SL → SL önce (konservatif)
  SORU E: --include-funding, default kapalı (8h UTC 00/08/16)
  SORU F: multi-symbol tasarım destekler; test tek-sembol

VARSAYIM (PO teyidi bekleniyor):
  - initial_equity default 10_000 (DURUM'da yok)
  - Fee: TP maker(0.0), SL/END taker(0.0002)
  - entry_slippage_bps 2.0 (SORU H-A)
  - min_sl_distance_pct 0.002 (SORU G-C)
  - R-multiple gross (fee hariç)
"""

from __future__ import annotations

import datetime as _dt
import logging
from collections import deque
from dataclasses import dataclass
from enum import Enum

from .replay_transport import OHLCVEvent, TickerEvent
from .strategy import Direction, EntrySignal

logger = logging.getLogger(__name__)

_CANDLE_SEC = 5
_FUNDING_HOURS_UTC = (0, 8, 16)


class ExitReason(str, Enum):
    TP = "TP"
    SL = "SL"
    END_OF_BACKTEST = "END_OF_BACKTEST"


@dataclass(frozen=True, slots=True)
class PositionSimConfig:
    # SORU B (DURUM §8)
    initial_equity: float = 10_000.0        # VARSAYIM
    risk_pct: float = 0.008                 # AnaYasa §3 TEST default
    # SORU A (DURUM §8)
    atr_period: int = 14
    sl_atr_multiplier: float = 0.5
    tp_r_multiple: float = 2.0
    max_sl_distance_pct: float = 0.025      # AnaYasa max_sl_distance
    min_sl_distance_pct: float = 0.002      # SORU G-C — VARSAYIM
    # SORU C (DURUM §8) — SORU H (A) fill slippage bps tabanlı
    entry_slippage_bps: float = 2.0         # VARSAYIM
    # Fee (DURUM §8)
    fee_taker: float = 0.0002
    fee_maker: float = 0.0
    # SORU E (DURUM §8)
    include_funding: bool = False
    # Concurrency (DURUM §8)
    max_positions_per_symbol: int = 1
    max_positions_global: int = 3           # TEST default


@dataclass(slots=True)
class Trade:
    symbol: str
    direction: Direction
    entry_ts_ms: int
    entry_price: float
    qty: float
    sl_price: float
    tp_price: float
    exit_ts_ms: int
    exit_price: float
    exit_reason: ExitReason
    fee_paid: float
    funding_paid: float
    pnl_gross: float
    pnl_net: float
    r_multiple: float

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "direction": self.direction.value,
            "entry_ts_ms": self.entry_ts_ms,
            "entry_price": self.entry_price,
            "qty": self.qty,
            "sl_price": self.sl_price,
            "tp_price": self.tp_price,
            "exit_ts_ms": self.exit_ts_ms,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason.value,
            "fee_paid": round(self.fee_paid, 8),
            "funding_paid": round(self.funding_paid, 8),
            "pnl_gross": round(self.pnl_gross, 8),
            "pnl_net": round(self.pnl_net, 8),
            "r_multiple": round(self.r_multiple, 4),
        }


@dataclass(slots=True)
class BacktestReport:
    initial_equity: float
    final_equity: float
    total_trades: int
    win_rate: float
    avg_r_multiple: float
    max_drawdown_pct: float
    total_return_pct: float

    def to_dict(self) -> dict:
        return {
            "initial_equity": round(self.initial_equity, 4),
            "final_equity": round(self.final_equity, 4),
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 4),
            "avg_r_multiple": round(self.avg_r_multiple, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "total_return_pct": round(self.total_return_pct, 4),
        }


@dataclass(slots=True)
class _Position:
    symbol: str
    direction: Direction
    entry_ts_ms: int
    entry_bucket_sec: int
    entry_price: float
    qty: float
    sl_price: float
    tp_price: float
    entry_fee: float
    funding_paid: float = 0.0


@dataclass(slots=True)
class _Candle5s:
    sec: int
    ts_ms: int
    open: float
    high: float
    low: float
    close: float


class PositionSimulator:
    def __init__(self, config: PositionSimConfig) -> None:
        self._cfg = config
        self._equity = float(config.initial_equity)
        cap = max(config.atr_period * 4, 100)
        self._candles: deque[_Candle5s] = deque(maxlen=cap)
        self._active: _Candle5s | None = None
        self._positions: dict[str, _Position] = {}
        self._trades: list[Trade] = []
        self._last_funding_rate: float = 0.0
        self._next_funding_ms: int | None = None

    # ---------------------------------------------------------- feeds

    def on_ohlcv(self, ev: OHLCVEvent) -> None:
        cfg = self._cfg
        if self._next_funding_ms is None:
            self._next_funding_ms = _next_funding_ts(ev.ts_ms)
        while ev.ts_ms >= self._next_funding_ms:
            if cfg.include_funding:
                self._apply_funding()
            self._next_funding_ms = _next_funding_ts(
                self._next_funding_ms + 1
            )

        bucket_sec = (ev.sec // _CANDLE_SEC) * _CANDLE_SEC
        if self._active is None:
            self._active = _Candle5s(
                sec=bucket_sec,
                ts_ms=bucket_sec * 1000,
                open=ev.open,
                high=ev.high,
                low=ev.low,
                close=ev.close,
            )
            return
        if bucket_sec > self._active.sec:
            self._finalize_active()
            self._active = _Candle5s(
                sec=bucket_sec,
                ts_ms=bucket_sec * 1000,
                open=ev.open,
                high=ev.high,
                low=ev.low,
                close=ev.close,
            )
        elif bucket_sec == self._active.sec:
            b = self._active
            if ev.high > b.high:
                b.high = ev.high
            if ev.low < b.low:
                b.low = ev.low
            b.close = ev.close
        # else: out-of-order, drop silently (backtest determinism)

    def on_ticker(self, ev: TickerEvent) -> None:
        self._last_funding_rate = float(ev.funding_rate or 0.0)

    def on_entry(self, signal: EntrySignal, symbol: str) -> bool:
        cfg = self._cfg
        if symbol in self._positions:
            return False
        if len(self._positions) >= cfg.max_positions_global:
            return False
        if cfg.max_positions_per_symbol < 1:
            return False
        atr = self._atr()
        if atr is None or atr <= 0.0:
            logger.debug("entry rejected: ATR not ready (%s)", symbol)
            return False
        signal_close = float(signal.price)
        if signal_close <= 0.0:
            return False
        sl_distance_raw = cfg.sl_atr_multiplier * atr
        sl_distance_cap = cfg.max_sl_distance_pct * signal_close
        sl_distance_floor = cfg.min_sl_distance_pct * signal_close
        sl_distance = max(
            min(sl_distance_raw, sl_distance_cap), sl_distance_floor
        )
        if sl_distance <= 0.0:
            return False

        slip_pct = self._slippage_pct()
        if signal.direction == Direction.LONG:
            entry_fill = signal_close * (1.0 + slip_pct)
            sl_price = entry_fill - sl_distance
            tp_price = entry_fill + cfg.tp_r_multiple * sl_distance
        else:
            entry_fill = signal_close * (1.0 - slip_pct)
            sl_price = entry_fill + sl_distance
            tp_price = entry_fill - cfg.tp_r_multiple * sl_distance

        risk_amount = self._equity * cfg.risk_pct
        qty = risk_amount / sl_distance
        if qty <= 0.0:
            return False
        entry_fee = entry_fill * qty * cfg.fee_taker
        bucket_sec = (signal.ts_ms // 1000 // _CANDLE_SEC) * _CANDLE_SEC
        self._positions[symbol] = _Position(
            symbol=symbol,
            direction=signal.direction,
            entry_ts_ms=signal.ts_ms,
            entry_bucket_sec=bucket_sec,
            entry_price=entry_fill,
            qty=qty,
            sl_price=sl_price,
            tp_price=tp_price,
            entry_fee=entry_fee,
        )
        return True

    def finalize(self, last_ts_ms: int, last_price: float) -> None:
        if self._active is not None:
            self._finalize_active()
        for symbol in list(self._positions.keys()):
            self._close_position(
                symbol, last_ts_ms, last_price, ExitReason.END_OF_BACKTEST
            )

    # ---------------------------------------------------------- accessors

    @property
    def trades(self) -> list[Trade]:
        return list(self._trades)

    @property
    def equity(self) -> float:
        return self._equity

    @property
    def open_positions(self) -> dict[str, _Position]:
        return dict(self._positions)

    def build_report(self) -> BacktestReport:
        cfg = self._cfg
        trades = self._trades
        n = len(trades)
        if n == 0:
            return BacktestReport(
                initial_equity=cfg.initial_equity,
                final_equity=self._equity,
                total_trades=0,
                win_rate=0.0,
                avg_r_multiple=0.0,
                max_drawdown_pct=0.0,
                total_return_pct=0.0,
            )
        wins = sum(1 for t in trades if t.pnl_net > 0.0)
        win_rate = wins / n
        avg_r = sum(t.r_multiple for t in trades) / n
        eq = float(cfg.initial_equity)
        peak = eq
        max_dd = 0.0
        for t in trades:
            eq += t.pnl_net
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0.0 else 0.0
            if dd > max_dd:
                max_dd = dd
        total_return = (
            (self._equity - cfg.initial_equity) / cfg.initial_equity
        )
        return BacktestReport(
            initial_equity=cfg.initial_equity,
            final_equity=self._equity,
            total_trades=n,
            win_rate=win_rate,
            avg_r_multiple=avg_r,
            max_drawdown_pct=max_dd,
            total_return_pct=total_return,
        )

    # ---------------------------------------------------------- internal

    def _slippage_pct(self) -> float:
        return self._cfg.entry_slippage_bps / 10_000.0

    def _atr(self) -> float | None:
        cfg = self._cfg
        if len(self._candles) < cfg.atr_period + 1:
            return None
        candles = list(self._candles)
        start = len(candles) - cfg.atr_period
        trs: list[float] = []
        for i in range(start, len(candles)):
            prev = candles[i - 1]
            cur = candles[i]
            tr = max(
                cur.high - cur.low,
                abs(cur.high - prev.close),
                abs(cur.low - prev.close),
            )
            trs.append(tr)
        if not trs:
            return None
        return sum(trs) / len(trs)

    def _finalize_active(self) -> None:
        b = self._active
        if b is None:
            return
        self._candles.append(b)
        self._active = None
        self._check_exits_on_candle(b)

    def _apply_funding(self) -> None:
        rate = self._last_funding_rate
        for pos in self._positions.values():
            notional = pos.entry_price * pos.qty
            if pos.direction == Direction.LONG:
                pos.funding_paid += rate * notional
            else:
                pos.funding_paid -= rate * notional

    def _check_exits_on_candle(self, c: _Candle5s) -> None:
        for symbol in list(self._positions.keys()):
            pos = self._positions[symbol]
            # entry bucket atlanır (entry close'unda açıldı; adil değil)
            if c.sec <= pos.entry_bucket_sec:
                continue
            if pos.direction == Direction.LONG:
                hit_sl = c.low <= pos.sl_price
                hit_tp = c.high >= pos.tp_price
                if hit_sl:
                    # SORU D: SL önce (konservatif)
                    self._close_position(
                        symbol, c.ts_ms, pos.sl_price, ExitReason.SL
                    )
                elif hit_tp:
                    self._close_position(
                        symbol, c.ts_ms, pos.tp_price, ExitReason.TP
                    )
            else:
                hit_sl = c.high >= pos.sl_price
                hit_tp = c.low <= pos.tp_price
                if hit_sl:
                    self._close_position(
                        symbol, c.ts_ms, pos.sl_price, ExitReason.SL
                    )
                elif hit_tp:
                    self._close_position(
                        symbol, c.ts_ms, pos.tp_price, ExitReason.TP
                    )

    def _close_position(
        self,
        symbol: str,
        ts_ms: int,
        exit_price: float,
        reason: ExitReason,
    ) -> None:
        pos = self._positions.pop(symbol, None)
        if pos is None:
            return
        cfg = self._cfg
        if pos.direction == Direction.LONG:
            pnl_gross = (exit_price - pos.entry_price) * pos.qty
        else:
            pnl_gross = (pos.entry_price - exit_price) * pos.qty
        exit_fee_rate = (
            cfg.fee_maker if reason == ExitReason.TP else cfg.fee_taker
        )
        exit_fee = exit_price * pos.qty * exit_fee_rate
        total_fee = pos.entry_fee + exit_fee
        pnl_net = pnl_gross - total_fee - pos.funding_paid
        r_dist = abs(pos.entry_price - pos.sl_price)
        if r_dist > 0.0:
            if pos.direction == Direction.LONG:
                r_mult = (exit_price - pos.entry_price) / r_dist
            else:
                r_mult = (pos.entry_price - exit_price) / r_dist
        else:
            r_mult = 0.0
        self._trades.append(Trade(
            symbol=symbol,
            direction=pos.direction,
            entry_ts_ms=pos.entry_ts_ms,
            entry_price=pos.entry_price,
            qty=pos.qty,
            sl_price=pos.sl_price,
            tp_price=pos.tp_price,
            exit_ts_ms=ts_ms,
            exit_price=exit_price,
            exit_reason=reason,
            fee_paid=total_fee,
            funding_paid=pos.funding_paid,
            pnl_gross=pnl_gross,
            pnl_net=pnl_net,
            r_multiple=r_mult,
        ))
        self._equity += pnl_net


def _next_funding_ts(ts_ms: int) -> int:
    """Return strictly-next 00/08/16 UTC boundary ms after ts_ms."""
    dt = _dt.datetime.fromtimestamp(ts_ms / 1000.0, tz=_dt.timezone.utc)
    dt = dt + _dt.timedelta(milliseconds=1)
    for h in _FUNDING_HOURS_UTC:
        if dt.hour < h:
            target = dt.replace(hour=h, minute=0, second=0, microsecond=0)
            return int(target.timestamp() * 1000)
    target = (dt + _dt.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int(target.timestamp() * 1000)