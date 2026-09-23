# src/trading/paper_math.py
# B3.3 — Paper position math core (pure functions; no side effects).
#
# SORU B3.3-A.1: shared between backtest PositionSimulator and
# PaperPositionManager to prevent parity drift. All formulas mirror
# src/backtest/position_sim.py exactly (see position_sim.on_entry,
# _close_position, build_report).
#
# Conventions:
#   direction: "LONG" | "SHORT" (str or str-Enum; strategy.Direction
#              is a str-Enum, so Direction.LONG == "LONG" is True)
#   exit_reason: "TP" | "SL" | "END_OF_BACKTEST"
#   fee_taker, fee_maker: rates (e.g. 0.0002)
#   entry_slippage_bps: basis points (e.g. 2.0)

from __future__ import annotations

LONG = "LONG"
SHORT = "SHORT"
TP = "TP"
SL = "SL"
END_OF_BACKTEST = "END_OF_BACKTEST"

_VALID_DIRECTIONS = frozenset({LONG, SHORT})
_VALID_EXITS = frozenset({TP, SL, END_OF_BACKTEST})


def apply_entry_slippage(
    last_price: float, direction: str, slippage_bps: float
) -> float:
    """B3.3-B.1: LONG price up, SHORT price down.
    Mirrors position_sim.on_entry slip application.
    Returns 0.0 if last_price <= 0.
    """
    if last_price <= 0.0:
        return 0.0
    pct = slippage_bps / 10_000.0
    if direction == LONG:
        return last_price * (1.0 + pct)
    return last_price * (1.0 - pct)


def compute_sl_distance(
    atr: float,
    price: float,
    *,
    sl_atr_multiplier: float,
    max_sl_distance_pct: float,
    min_sl_distance_pct: float,
) -> float:
    """Mirror of position_sim.on_entry SL distance computation.
    sl_distance = clamp(sl_atr_multiplier * atr,
                        min_pct * price, max_pct * price)
    Returns 0.0 if atr <= 0 or price <= 0.
    """
    if atr <= 0.0 or price <= 0.0:
        return 0.0
    raw = sl_atr_multiplier * atr
    cap = max_sl_distance_pct * price
    floor = min_sl_distance_pct * price
    return max(min(raw, cap), floor)


def compute_sl_price(
    entry_fill: float, sl_distance: float, direction: str
) -> float:
    """B2c: LONG sl below, SHORT sl above."""
    if direction == LONG:
        return entry_fill - sl_distance
    return entry_fill + sl_distance


def compute_tp_price(
    entry_fill: float,
    sl_distance: float,
    tp_r_multiple: float,
    direction: str,
) -> float:
    """B2c: TP = entry ± tp_r_multiple * sl_distance."""
    if direction == LONG:
        return entry_fill + tp_r_multiple * sl_distance
    return entry_fill - tp_r_multiple * sl_distance


def compute_qty(equity: float, risk_pct: float, sl_distance: float) -> float:
    """B2c SORU B: qty = (equity * risk_pct) / |entry - SL|.
    Returns 0.0 if sl_distance <= 0 or equity <= 0.
    """
    if sl_distance <= 0.0 or equity <= 0.0:
        return 0.0
    return (equity * risk_pct) / sl_distance


def compute_entry_fee(entry_fill: float, qty: float, fee_taker: float) -> float:
    return entry_fill * qty * fee_taker


def compute_exit_fee(
    exit_price: float,
    qty: float,
    fee_taker: float,
    fee_maker: float,
    exit_reason: str,
) -> float:
    """TP -> maker; SL/END -> taker (position_sim._close_position)."""
    rate = fee_maker if exit_reason == TP else fee_taker
    return exit_price * qty * rate


def compute_pnl_gross(
    entry_fill: float, exit_price: float, qty: float, direction: str
) -> float:
    if direction == LONG:
        return (exit_price - entry_fill) * qty
    return (entry_fill - exit_price) * qty


def compute_r_multiple(
    entry_fill: float,
    exit_price: float,
    sl_price: float,
    direction: str,
) -> float:
    r_dist = abs(entry_fill - sl_price)
    if r_dist <= 0.0:
        return 0.0
    if direction == LONG:
        return (exit_price - entry_fill) / r_dist
    return (entry_fill - exit_price) / r_dist


def compute_atr(candles: list, atr_period: int) -> float | None:
    """Simple-average TR over atr_period candles.
    Mirror of position_sim.PositionSimulator._atr.
    candles: sequence of objects with .high, .low, .close attributes.
    Returns None if len(candles) < atr_period + 1.
    """
    if len(candles) < atr_period + 1:
        return None
    start = len(candles) - atr_period
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


def next_funding_ts_ms(ts_ms: int) -> int:
    """Next 00/08/16 UTC boundary strictly after ts_ms.
    Mirror of position_sim._next_funding_ts.
    """
    import datetime as _dt

    dt = _dt.datetime.fromtimestamp(ts_ms / 1000.0, tz=_dt.timezone.utc)
    dt = dt + _dt.timedelta(milliseconds=1)
    for h in (0, 8, 16):
        if dt.hour < h:
            target = dt.replace(hour=h, minute=0, second=0, microsecond=0)
            return int(target.timestamp() * 1000)
    target = (dt + _dt.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int(target.timestamp() * 1000)


def compute_funding_delta(
    rate: float, notional: float, direction: str
) -> float:
    """Position funding delta (positive = paid by position).
    LONG pays positive rate; SHORT receives positive rate
    (position_sim._apply_funding).
    """
    signed = rate * notional
    if direction == LONG:
        return signed
    return -signed