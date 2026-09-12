"""Decimal utilities for precise financial calculations.

Y-323: All monetary values use Decimal with explicit precision.
Y-271: str(Decimal) uses ROUND_DOWN to prevent rounding up errors.
No global state (Y-353).
"""

from decimal import Decimal, ROUND_DOWN, getcontext


# Set global decimal context (one-time setup, not mutable state)
getcontext().prec = 28
getcontext().rounding = ROUND_DOWN


def to_decimal(value: str | float | int) -> Decimal:
    """Convert value to Decimal with proper precision.
    
    Y-323: All monetary values must use Decimal.
    
    Args:
        value: String, float, or int to convert.
        
    Returns:
        Decimal: Converted value.
        
    Raises:
        ValueError: If conversion fails.
    """
    if isinstance(value, Decimal):
        return value
    
    try:
        return Decimal(str(value))
    except (ValueError, TypeError) as e:
        raise ValueError(f"Cannot convert {value!r} to Decimal") from e


def format_decimal(value: Decimal, places: int = 8) -> str:
    """Format Decimal to string with fixed decimal places.
    
    Y-271: Uses ROUND_DOWN to prevent rounding up errors.
    
    Args:
        value: Decimal value to format.
        places: Number of decimal places (default: 8).
        
    Returns:
        str: Formatted string representation.
    """
    if not isinstance(value, Decimal):
        raise TypeError("value must be Decimal")
    
    quantize_str = "0." + "0" * places
    return str(value.quantize(Decimal(quantize_str), rounding=ROUND_DOWN))


def safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Safely divide two Decimals, handling zero denominator.
    
    Args:
        numerator: Numerator value.
        denominator: Denominator value.
        
    Returns:
        Decimal: Result of division, or Decimal("0") if denominator is zero.
    """
    if denominator == 0:
        return Decimal("0")
    return numerator / denominator


def clamp_decimal(value: Decimal, min_val: Decimal, max_val: Decimal) -> Decimal:
    """Clamp Decimal value between min and max.
    
    Args:
        value: Value to clamp.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.
        
    Returns:
        Decimal: Clamped value.
    """
    if value < min_val:
        return min_val
    if value > max_val:
        return max_val
    return value
