# YAMA Y-263: bypass YASAK FATAL
# YAMA Y-275: SINGLE GLOBAL rate 8 burst 15, no separate buckets, no bypass
# YAMA Y-326: await token_bucket.acquire() - async acquire
# YAMA Y-358: asyncio.Lock, threading.Lock YASAK

"""
Token bucket rate limiter.

Y-275: SINGLE GLOBAL rate 8 burst 15, no separate buckets, no bypass.
Y-326: await token_bucket.acquire() async.
Y-358: asyncio.Lock only.
Y-263: bypass forbidden.
"""

from __future__ import annotations

import asyncio
import time
from typing import Final

class TokenBucket:
    """
    Normal class (not dataclass).

    RATE=8, BURST=15 final.
    """

    RATE: Final[int] = 8
    BURST: Final[int] = 15

    def __init__(self) -> None:
        # Y-275: assert single global
        assert self.RATE == 8 and self.BURST == 15, "FATAL: Y-275 rate 8 burst 15 only"
        self._rate: float = float(self.RATE)
        self._burst: float = float(self.BURST)
        self._tokens: float = float(self.BURST)
        self._last_mono: float = time.monotonic()
        self._lock: asyncio.Lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_mono
        # cap at burst
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_mono = now

    async def acquire(self, tokens: float = 1.0) -> bool:
        """
        Acquire tokens, wait if not enough.

        Y-275: no bypass.
        Y-326: async acquire.
        Recursion forbidden, while loop mandatory.
        """
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
                needed = tokens - self._tokens
                wait_time = needed / self._rate

            # sleep outside lock (Y-327 logic)
            await asyncio.sleep(wait_time)

    def get_tokens(self) -> float:
        """Return current tokens after refill."""
        self._refill()
        return self._tokens