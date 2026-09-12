# YAMA Y-353: Stateless utils - no global mutable state, pure functions
# YAMA Y-323: ROUND_DOWN required - HALF_UP forbidden for price/qty quantize
# YAMA DECIMAL-QUANTIZE: Decimal quantize with str(Decimal) ROUND_DOWN price_precision qty_precision separate - float FATAL
# YAMA Y-260: Slippage leverage adjusted uses Decimal min(0.03, 0.10/lev)

"""
Decimal utils.

All price/qty operations must use Decimal quantize with str(Decimal) and ROUND_DOWN (Y-323).
price_precision and qty_precision separate.
Float for price/qty is FATAL.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

def quantize_price(price: Decimal | str | float, precision: Decimal) -> Decimal:
    """
    Quantize price with str(Decimal) using ROUND_DOWN (Y-323).

    Args:
        price: Decimal or str, float is converted via str() but WARNING
        precision: e.g. Decimal("0.01")

    Returns:
        Quantized Decimal with ROUND_DOWN
    """
    raise NotImplementedError("FAZ 1")

def quantize_qty(qty: Decimal | str | float, precision: Decimal) -> Decimal:
    """
    Quantize qty with str(Decimal) using ROUND_DOWN (Y-323) separate from price precision.
    """
    raise NotImplementedError("FAZ 1")

def to_decimal(value: str | int | float | Decimal) -> Decimal:
    """Convert to Decimal via str(value) to avoid float FATAL."""
    raise NotImplementedError("FAZ 1")

def is_valid_price_precision(price: Decimal, tick_size: Decimal) -> bool:
    """Check price aligns with tick_size - FATAL if not."""
    raise NotImplementedError("FAZ 1")

def is_valid_qty_precision(qty: Decimal, step_size: Decimal) -> bool:
    """Check qty aligns with step_size."""
    raise NotImplementedError("FAZ 1")

def compute_slippage_pct(leverage: int) -> Decimal:
    """
    Compute slippage pct leverage adjusted (Y-260).

    Formula: min(Decimal('0.03'), Decimal('0.10') / leverage)
    Example: 20x = 0.5%
    """
    raise NotImplementedError("FAZ 1")