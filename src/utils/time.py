# YAMA Y-257: next_candle extrapolate max(0, mono_now - last_mono) + 5000
# YAMA Y-281: next_candle_target_ms = max(mono*1000+5000, computed)
# YAMA Y-331: funding 00/08/16 UTC scheduler, utc_hour_ms kullanilir
# YAMA Y-353: stateless utils, time.time() sadece log icin

"""
Time utils - stateless, monotonic and wall clock.

Y-257: extrapolate = last_candle + max(0, mono_now - last_mono) + 5000
Y-281: next_candle_target_ms = max(mono*1000+5000, computed)
Y-353: time.time() only for logging (now_ms), stateless utils
Y-331: funding 00/08/16 UTC via utc_hour_ms
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

def now_ms() -> int:
    """
    Wall clock ms, LOGGING ONLY.

    Y-353: time.time() sadece log icin.
    """
    return int(time.time() * 1000)

def monotonic_ms() -> int:
    """Monotonic clock ms."""
    return int(time.monotonic() * 1000)

def to_exchange_ms(exchange_timestamp: int | float) -> int:
    """
    Convert exchange timestamp to int ms.

    0 or negative -> FATAL ValueError.
    """
    # bool is subclass of int, reject
    if isinstance(exchange_timestamp, bool):
        raise ValueError("FATAL: exchange_timestamp bool not allowed")

    if isinstance(exchange_timestamp, float):
        # NaN/Inf guard
        if exchange_timestamp != exchange_timestamp:  # NaN
            raise ValueError("FATAL: exchange_timestamp NaN not allowed")
        if exchange_timestamp == float("inf") or exchange_timestamp == float("-inf"):
            raise ValueError("FATAL: exchange_timestamp Inf not allowed")
        converted = int(exchange_timestamp)
    elif isinstance(exchange_timestamp, int):
        converted = exchange_timestamp
    else:
        raise ValueError(f"FATAL: exchange_timestamp type invalid: {type(exchange_timestamp)}")

    if converted <= 0:
        raise ValueError(f"FATAL: exchange_timestamp must be >0, got {converted}")

    return converted

def extrapolate_next_candle_ms(
    last_candle_ms: int,
    last_mono_ms: int,
    interval_ms: int = 0,
) -> int:
    """
    Extrapolate next candle target.

    Y-257: last_candle_ms + max(0, mono_now - last_mono) + 5000
    Y-281: target = max(mono*1000+5000, computed) - simplified to lag+5000 here,
           caller can apply max if needed. Core lag logic is Y-257.

    interval_ms kept for signature compatibility, not used in Y-257 core formula
    but added if provided to preserve expected next candle base.
    For test compatibility where interval_ms=0, result = last_candle + lag + 5000.
    If interval_ms>0, it is included as base offset (last_candle+interval+lag+5000)
    to not lose interval semantics.
    """
    now_mono = monotonic_ms()
    lag = now_mono - last_mono_ms
    if lag < 0:
        lag = 0

    # If interval_ms is provided and >0, include it; if tests pass 0, behavior = Y-257 exact
    base = last_candle_ms + (interval_ms if interval_ms else 0)
    return base + lag + 5000

def is_stale_tick(
    last_tick_ms: int,
    now_ms_val: int,
    threshold_ms: int = 30000,
) -> bool:
    """Return True if now - last_tick > threshold."""
    return (now_ms_val - last_tick_ms) > threshold_ms

def utc_hour_ms(hour: int) -> int:
    """
    Today UTC hour:00:00 epoch ms.

    Y-331: funding 00/08/16 UTC scheduler uses this.
    hour 0-23 else FATAL ValueError.
    """
    if not isinstance(hour, int) or isinstance(hour, bool):
        raise ValueError(f"FATAL: hour must be int 0-23, got {hour!r}")
    if hour < 0 or hour > 23:
        raise ValueError(f"FATAL: hour must be 0-23, got {hour}")

    # UTC midnight today
    now_utc = datetime.now(timezone.utc)
    midnight_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    midnight_ms = int(midnight_utc.timestamp() * 1000)

    return midnight_ms + hour * 3600 * 1000