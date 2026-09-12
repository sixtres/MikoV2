"""Time utilities for candle and interval calculations.

Y-257: next_candle calculates next candle boundary correctly.
Y-281: All interval calculations use max(0, ...) + 5000ms buffer.
No global state (Y-353).
"""

from datetime import datetime, timezone


MS_PER_SECOND: int = 1_000
MS_PER_MINUTE: int = 60 * MS_PER_SECOND
MS_PER_HOUR: int = 60 * MS_PER_MINUTE
MS_PER_DAY: int = 24 * MS_PER_HOUR


def now_ms() -> int:
    """Get current UTC timestamp in milliseconds.
    
    Returns:
        int: Current UTC time in ms since epoch.
    """
    return int(datetime.now(timezone.utc).timestamp() * MS_PER_SECOND)


def next_candle(timestamp_ms: int, interval_minutes: int) -> int:
    """Calculate next candle boundary in milliseconds.
    
    Y-257: Correctly handles edge cases at boundaries.
    
    Args:
        timestamp_ms: Current timestamp in ms.
        interval_minutes: Candle interval in minutes (1, 5, 15, 60, etc.).
        
    Returns:
        int: Next candle boundary timestamp in ms.
    """
    interval_ms = interval_minutes * MS_PER_MINUTE
    
    # Floor to current candle start
    current_candle = (timestamp_ms // interval_ms) * interval_ms
    
    # Next candle is current + interval
    next_candle_ts = current_candle + interval_ms
    
    return next_candle_ts


def ms_until_next_candle(timestamp_ms: int, interval_minutes: int) -> int:
    """Calculate milliseconds until next candle.
    
    Y-281: Uses max(0, ...) + 5000ms buffer for safety.
    
    Args:
        timestamp_ms: Current timestamp in ms.
        interval_minutes: Candle interval in minutes.
        
    Returns:
        int: Milliseconds until next candle (with 5000ms buffer).
    """
    next_candle_ts = next_candle(timestamp_ms, interval_minutes)
    remaining = next_candle_ts - timestamp_ms
    
    # Y-281: max(0, ...) + 5000ms buffer
    return max(0, remaining) + 5000


def floor_to_candle(timestamp_ms: int, interval_minutes: int) -> int:
    """Floor timestamp to current candle start.
    
    Args:
        timestamp_ms: Timestamp in ms.
        interval_minutes: Candle interval in minutes.
        
    Returns:
        int: Floored timestamp to candle start.
    """
    interval_ms = interval_minutes * MS_PER_MINUTE
    return (timestamp_ms // interval_ms) * interval_ms


def is_candle_boundary(timestamp_ms: int, interval_minutes: int) -> bool:
    """Check if timestamp is exactly on candle boundary.
    
    Args:
        timestamp_ms: Timestamp in ms.
        interval_minutes: Candle interval in minutes.
        
    Returns:
        bool: True if on boundary.
    """
    interval_ms = interval_minutes * MS_PER_MINUTE
    return timestamp_ms % interval_ms == 0
