"""Logging utilities with rate-limited trim.

Y-348: Rate-limited log trimming to prevent log flooding.
WARNING level logs are trimmed if rate exceeds threshold.
No global state (Y-353).
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Final


# Y-348: Rate limit configuration
_MAX_WARNING_RATE: Final[int] = 10  # Max warnings per second
_TRIM_THRESHOLD: Final[int] = 1000  # Trim after this many lines


@dataclass
class RateLimiter:
    """Rate limiter for log messages.
    
    Y-348: Prevents log flooding by limiting message rate.
    """
    
    max_rate: int  # Max messages per second
    window_start: float = field(default_factory=time.time)
    count: int = 0
    
    def should_log(self) -> bool:
        """Check if message should be logged based on rate.
        
        Returns:
            bool: True if within rate limit.
        """
        now = time.time()
        
        # Reset window if expired
        if now - self.window_start >= 1.0:
            self.window_start = now
            self.count = 0
        
        # Check rate limit
        if self.count >= self.max_rate:
            return False
        
        self.count += 1
        return True


class TrimmedLogger:
    """Logger with rate-limited trim.
    
    Y-348: WARNING logs are rate-limited and trimmed.
    """
    
    def __init__(self, name: str, max_rate: int = _MAX_WARNING_RATE) -> None:
        """Initialize trimmed logger.
        
        Args:
            name: Logger name.
            max_rate: Max warnings per second.
        """
        self._logger = logging.getLogger(name)
        self._warning_limiter = RateLimiter(max_rate=max_rate)
        self._trim_count: int = 0
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message."""
        self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message."""
        self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning with rate limiting.
        
        Y-348: Warnings are rate-limited to prevent flooding.
        """
        if self._warning_limiter.should_log():
            self._logger.warning(msg, *args, **kwargs)
        else:
            self._trim_count += 1
            if self._trim_count >= _TRIM_THRESHOLD:
                # Log trim notification
                self._logger.warning(
                    f"Trimmed {self._trim_count} warning(s) due to rate limit (Y-348)"
                )
                self._trim_count = 0
    
    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message (not rate-limited)."""
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message (not rate-limited)."""
        self._logger.critical(msg, *args, **kwargs)


def create_logger(name: str, level: int = logging.INFO) -> TrimmedLogger:
    """Create configured trimmed logger.
    
    Args:
        name: Logger name.
        level: Logging level (default: INFO).
        
    Returns:
        TrimmedLogger: Configured logger.
    """
    logger = TrimmedLogger(name)
    
    # Configure handler
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    
    # Set level
    logger._logger.setLevel(level)
    logger._logger.addHandler(handler)
    
    return logger
