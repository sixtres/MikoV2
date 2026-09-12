# YAMA Y-260: slippage min(0.03, 0.10/leverage)
# YAMA Y-271: Decimal f-string YASAK, quantize str(Decimal.quantize)
# YAMA Y-323: ROUND_DOWN required, HALF_UP YASAK, str(Decimal) not float

"""
Decimal utils - safe quantization and validation.

Y-323: ROUND_DOWN only, HALF_UP forbidden, Decimal(str()) not float().
Y-271: Decimal f-string forbidden.
Y-260: slippage min(0.03, 0.10/leverage)
"""

from __future__ import annotations

import math
from decimal import ROUND_DOWN, Decimal
from typing import Union

DecimalLike = Union[Decimal, str, int, float]
PrecisionLike = Union[Decimal, int, str]

def _resolve_precision(precision: PrecisionLike) -> Decimal:
    """Resolve precision to Decimal quantizer."""
    if isinstance(precision, Decimal):
        return precision
    if isinstance(precision, int):
        # scaleb avoids f-string, handles int -> 1e-precision
        return Decimal("1").scaleb(-precision)
    # str or other -> Decimal via str()
    return Decimal(str(precision))

def to_decimal(value: DecimalLike) -> Decimal:
    """
    Convert value to Decimal via str() path.

    Y-323: str(Decimal) required, direct float() forbidden.
    NaN/Inf -> FATAL ValueError.
    """
    if isinstance(value, Decimal):
        if value.is_nan() or value.is_infinite():
            raise ValueError(f"FATAL: NaN/Inf Decimal not allowed: {value!r}")
        return value

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"FATAL: NaN/Inf float not allowed: {value!r}")
        return Decimal(str(value))

    if isinstance(value, int):
        return Decimal(str(value))

    if isinstance(value, str):
        d = Decimal(value)
        if d.is_nan() or d.is_infinite():
            raise ValueError(f"FATAL: NaN/Inf str not allowed: {value!r}")
        return d

    # fallback for other types (e.g. numpy) -> str path
    s = str(value)
    d = Decimal(s)
    if d.is_nan() or d.is_infinite():
        raise ValueError(f"FATAL: NaN/Inf value not allowed: {value!r}")
    return d

def quantize_price(price: DecimalLike, precision: PrecisionLike) -> Decimal:
    """
    Quantize price with ROUND_DOWN.

    Y-323: ROUND_DOWN required, HALF_UP forbidden.
    Y-271: Decimal f-string forbidden, use quantize directly.
    """
    d = to_decimal(price)
    q = _resolve_precision(precision)
    return d.quantize(q, rounding=ROUND_DOWN)

def quantize_qty(qty: DecimalLike, precision: PrecisionLike) -> Decimal:
    """
    Quantize qty with ROUND_DOWN.

    Y-323: ROUND_DOWN required.
    """
    d = to_decimal(qty)
    q = _resolve_precision(precision)
    return d.quantize(q, rounding=ROUND_DOWN)

def is_valid_price_precision(price: DecimalLike, tick_size: DecimalLike) -> bool:
    """
    Check price % tick_size == 0.

    Y-323: Decimal mod check via Decimal.
    """
    p = to_decimal(price)
    t = to_decimal(tick_size)
    if t == Decimal("0"):
        return False
    return (p % t) == Decimal("0")

def is_valid_qty_precision(qty: DecimalLike, step_size: DecimalLike) -> bool:
    """
    Check qty % step_size == 0.
    """
    q = to_decimal(qty)
    s = to_decimal(step_size)
    if s == Decimal("0"):
        return False
    return (q % s) == Decimal("0")

def compute_slippage_pct(leverage: int | float | Decimal) -> Decimal:
    """
    Y-260: min(0.03, 0.10/leverage).

    leverage via str() path, no direct float().
    """
    lev = to_decimal(leverage)
    if lev == Decimal("0"):
        raise ValueError("FATAL: leverage 0 not allowed")
    # Decimal('0.10') / lev via str path already handled
    ratio = Decimal("0.10") / lev
    ceiling = Decimal("0.03")
    return ceiling if ceiling < ratio else ratio