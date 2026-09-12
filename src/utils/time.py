# YAMA Y-257: Monotonic fallback - next_candle extrapolate max(0, mono_now - last_mono) + 5000, exchange_timestamp primary
# YAMA Y-353: Stateless utils - no global mutable state

"""
Time utils.

Handles exchange timestamp as primary time_source with monotonic fallback.
- last_local_tick_monotonic
- next_candle extrapolate max(0) + 5000 (Y-257)
- funding UTC 00/08/16
"""

from __future__ import annotations

import time

def now_ms() -> int:
    """
    Return current epoch ms for LOGGING ONLY.

    Runtime must use monotonic_ms() instead - wall clock can go backward
    (NTP adjust, DST). AnaYasa rule: time.time() only for logs.
    """
    raise NotImplementedError("FAZ 1")

def monotonic_ms() -> int:
    """Return monotonic ms - never goes backward."""
    raise NotImplementedError("FAZ 1")

def to_exchange_ms(exchange_timestamp: int | float) -> int:
    """Convert exchange timestamp to ms int - primary time_source."""
    raise NotImplementedError("FAZ 1")

def extrapolate_next_candle_ms(
    last_candle_ms: int, last_mono_ms: int, interval_ms: int
) -> int:
    """
    Extrapolate next candle time (Y-257).

    Formula: last_candle_ms + max(0, mono_now - last_mono) + 5000
    Fallback when exchange timestamp missing.
    """
    raise NotImplementedError("FAZ 1")

def is_stale_tick(last_tick_ms: int, now_ms_val: int, threshold_ms: int = 30000) -> bool:
    """Check if tick is stale >30s - health check."""
    raise NotImplementedError("FAZ 1")

def utc_hour_ms(hour: int) -> int:
    """
    Return epoch ms of today's UTC hour boundary.

    Used by funding scheduler for 00/08/16 UTC (Y-331).
    Example: utc_hour_ms(8) returns today's 08:00:00 UTC epoch ms.
    """
    raise NotImplementedError("FAZ 1")