# YAMA Y-257: next_candle extrapolate
# YAMA Y-281: next_candle_target_ms
# YAMA Y-331: funding 00/08/16 UTC
# YAMA Y-353: stateless utils

"""
Tests for src.utils.time
"""

import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.utils.time import (
    extrapolate_next_candle_ms,
    is_stale_tick,
    monotonic_ms,
    now_ms,
    to_exchange_ms,
    utc_hour_ms,
)

def test_now_ms_positive():
    # Y-353: logging only, positive ms
    result = now_ms()
    assert isinstance(result, int)
    assert result > 0

def test_monotonic_ms_monotonic():
    # monotonic should not go backwards
    m1 = monotonic_ms()
    time.sleep(0.01)
    m2 = monotonic_ms()
    assert m2 >= m1

def test_to_exchange_ms_int():
    assert to_exchange_ms(1710000000000) == 1710000000000

def test_to_exchange_ms_float():
    assert to_exchange_ms(1710000000000.9) == 1710000000000

def test_to_exchange_ms_zero_fatal():
    with pytest.raises(ValueError, match="FATAL"):
        to_exchange_ms(0)

def test_to_exchange_ms_negative_fatal():
    with pytest.raises(ValueError, match="FATAL"):
        to_exchange_ms(-1000)

def test_to_exchange_ms_negative_float_fatal():
    with pytest.raises(ValueError, match="FATAL"):
        to_exchange_ms(-1.5)

def test_extrapolate_no_lag():
    # Y-257: mono_now = last_mono -> +5000
    last_candle = 1000000
    last_mono = 5000
    with patch("src.utils.time.monotonic_ms", return_value=last_mono):
        result = extrapolate_next_candle_ms(last_candle, last_mono, 0)
    assert result == last_candle + 5000

def test_extrapolate_with_lag():
    # Y-257: mono_now - last_mono = 1000 -> +6000
    last_candle = 1000000
    last_mono = 5000
    with patch("src.utils.time.monotonic_ms", return_value=6000):
        result = extrapolate_next_candle_ms(last_candle, last_mono, 0)
    assert result == last_candle + 1000 + 5000

def test_extrapolate_negative_lag():
    # Y-257: mono_now < last_mono -> max(0) = 0 -> +5000
    last_candle = 1000000
    last_mono = 10000
    with patch("src.utils.time.monotonic_ms", return_value=5000):
        result = extrapolate_next_candle_ms(last_candle, last_mono, 0)
    assert result == last_candle + 5000

def test_is_stale_tick_true():
    last = 0
    now = 40000
    assert is_stale_tick(last, now, threshold_ms=30000) is True

def test_is_stale_tick_false():
    last = 10000
    now = 20000
    assert is_stale_tick(last, now, threshold_ms=30000) is False

def test_is_stale_tick_custom_threshold():
    last = 0
    now = 10000
    assert is_stale_tick(last, now, threshold_ms=5000) is True
    assert is_stale_tick(last, now, threshold_ms=15000) is False

def test_utc_hour_ms_hour_0():
    # Y-331: midnight today
    result = utc_hour_ms(0)
    dt = datetime.fromtimestamp(result / 1000, tz=timezone.utc)
    assert dt.hour == 0
    assert dt.minute == 0
    assert dt.second == 0

def test_utc_hour_ms_hour_8():
    # Y-331: funding 08 UTC
    r0 = utc_hour_ms(0)
    r8 = utc_hour_ms(8)
    assert r8 - r0 == 8 * 3600 * 1000
    dt = datetime.fromtimestamp(r8 / 1000, tz=timezone.utc)
    assert dt.hour == 8

def test_utc_hour_ms_hour_16():
    # Y-331: funding 16 UTC
    r0 = utc_hour_ms(0)
    r16 = utc_hour_ms(16)
    assert r16 - r0 == 16 * 3600 * 1000
    dt = datetime.fromtimestamp(r16 / 1000, tz=timezone.utc)
    assert dt.hour == 16

def test_utc_hour_ms_invalid_negative_fatal():
    with pytest.raises(ValueError, match="FATAL"):
        utc_hour_ms(-1)

def test_utc_hour_ms_invalid_24_fatal():
    with pytest.raises(ValueError, match="FATAL"):
        utc_hour_ms(24)

def test_utc_hour_ms_invalid_25_fatal():
    with pytest.raises(ValueError, match="FATAL"):
        utc_hour_ms(25)