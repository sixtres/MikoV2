# YAMA Y-260: slippage min(0.03, 0.10/leverage)
# YAMA Y-271: Decimal f-string YASAK
# YAMA Y-323: ROUND_DOWN required, HALF_UP YASAK

"""
Tests for src.utils.decimal

pytest only, no asyncio.
"""

import math
from decimal import Decimal

import pytest

from src.utils.decimal import (
    compute_slippage_pct,
    is_valid_price_precision,
    is_valid_qty_precision,
    quantize_price,
    quantize_qty,
    to_decimal,
)

# --- quantize_price ---

def test_quantize_price_round_down():
    # Y-323: ROUND_DOWN, 100.005 -> 100.00 not 100.01 (HALF_UP forbidden)
    result = quantize_price("100.005", Decimal("0.01"))
    assert result == Decimal("100.00")

def test_quantize_price_str_input():
    # Y-323: str and Decimal input same result via str() path
    r_str = quantize_price("100.005", Decimal("0.01"))
    r_dec = quantize_price(Decimal("100.005"), Decimal("0.01"))
    assert r_str == r_dec == Decimal("100.00")

# --- quantize_qty ---

def test_quantize_qty_separate_precision():
    # Y-323: price .01 vs qty .001 separate
    price_q = quantize_price("1.2345", Decimal("0.01"))
    qty_q = quantize_qty("1.2345", Decimal("0.001"))
    assert price_q == Decimal("1.23")
    assert qty_q == Decimal("1.234")

def test_quantize_qty_round_down_int_precision():
    # int precision 3 -> 1e-3 = 0.001
    result = quantize_qty("1.9999", 3)
    assert result == Decimal("1.999")

# --- to_decimal ---

def test_to_decimal_from_float():
    # Y-323: float via str() path
    result = to_decimal(100.005)
    assert result == Decimal("100.005")
    assert isinstance(result, Decimal)

def test_to_decimal_nan_fatal():
    # Y-323: NaN -> FATAL ValueError
    with pytest.raises(ValueError, match="FATAL"):
        to_decimal(float("nan"))

def test_to_decimal_inf_fatal():
    # Y-323: Inf -> FATAL ValueError
    with pytest.raises(ValueError, match="FATAL"):
        to_decimal(float("inf"))

def test_to_decimal_decimal_nan_fatal():
    with pytest.raises(ValueError, match="FATAL"):
        to_decimal(Decimal("NaN"))

# --- is_valid_price_precision ---

def test_is_valid_price_precision_exact():
    # 100.00 % 0.01 == 0 -> True
    assert is_valid_price_precision("100.00", "0.01") is True

def test_is_valid_price_precision_invalid():
    # Y-323: 100.005 % 0.01 != 0 -> False
    assert is_valid_price_precision("100.005", "0.01") is False

def test_is_valid_qty_precision_exact():
    assert is_valid_qty_precision("1.002", "0.001") is True

def test_is_valid_qty_precision_invalid():
    assert is_valid_qty_precision("1.0025", "0.001") is False

# --- compute_slippage_pct Y-260 ---

def test_compute_slippage_5x():
    # Y-260: 0.10/5 = 0.02 -> min(0.03, 0.02) = 0.02
    result = compute_slippage_pct(5)
    assert result == Decimal("0.02")

def test_compute_slippage_20x():
    # Y-260: 0.10/20 = 0.005
    result = compute_slippage_pct(20)
    assert result == Decimal("0.005")

def test_compute_slippage_30x():
    # Y-260: min(0.03, 0.10/30) = 0.10/30 = 0.00333...
    result = compute_slippage_pct(30)
    expected = Decimal("0.10") / Decimal("30")
    assert result == expected
    assert result < Decimal("0.03")

def test_compute_slippage_leverage_ceiling():
    # Y-260: 3x -> 0.10/3 = 0.0333... ceiling 0.03
    result = compute_slippage_pct(3)
    assert result == Decimal("0.03")

def test_compute_slippage_1x_ceiling():
    # 1x -> 0.10 -> capped to 0.03
    result = compute_slippage_pct(1)
    assert result == Decimal("0.03")