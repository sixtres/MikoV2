# YAMA Y-251: preallocated numpy float64[5000] hard cap, low-water 4000
# YAMA Y-252: searchsorted bids -price, asks price separate
# YAMA Y-253: RLock for L2Buffer - apply_batch calls trim() reentrant, asyncio.Lock deadlock
# YAMA Y-313: on_snapshot seq_epoch single increment
# YAMA Y-314: per-symbol seq_epoch defaultdict, expected_seq, pre_sync_queue, _seq_lock reset on reconnect
# YAMA Y-317a: trim sondan kes, 1000'lik blok chunk
# YAMA Y-332: TEK SAYAC batch_bids/batch_asks birlesik sayac
# YAMA Y-344: OBI aktif len kullanir, fixed 5000 varsayimi YASAK
# YAMA Y-348: trim WARNING rate-limited her 100 trim - log flooding onle
# YAMA Y-352: pre_sync_queue append eksik fix
# YAMA Y-353: Stateless - books dict via DI, no global mutable
# YAMA Y-360: np.searchsorted O(log n), Python for/list.sort FATAL - bulk C-slice

"""
L2 orderbook buffer with preallocated numpy arrays.

Per-symbol L2 buffer with RLock (reentrant needed for apply_batch->trim).
- Preallocated float64[5000] hard cap, low-water 4000 (Y-251)
- searchsorted for bids -price, asks price (Y-252, Y-360) O(log n)
- Trim farthest levels in 1000-block chunks (Y-317a)
- OBI uses active len not fixed 5000 (Y-344)
- Python for loop for buffer mutation FATAL, use bulk C-slice
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Final

import numpy as np

@dataclass(slots=True)
class L2Book:
    """Per-symbol L2 buffer with preallocated numpy arrays."""

    symbol: str
    bids_price: np.ndarray = field(
        default_factory=lambda: np.zeros(5000, dtype=np.float64)
    )
    bids_qty: np.ndarray = field(
        default_factory=lambda: np.zeros(5000, dtype=np.float64)
    )
    asks_price: np.ndarray = field(
        default_factory=lambda: np.zeros(5000, dtype=np.float64)
    )
    asks_qty: np.ndarray = field(
        default_factory=lambda: np.zeros(5000, dtype=np.float64)
    )
    bids_len: int = 0
    asks_len: int = 0
    lock: threading.RLock = field(default_factory=threading.RLock) # Y-253
    seq_epoch: dict = field(default_factory=lambda: defaultdict(int)) # Y-314
    expected_seq: dict = field(default_factory=dict) # Y-314
    pre_sync_queue: dict = field(
        default_factory=lambda: defaultdict(list)
    ) # Y-314 + Y-352
    _seq_lock: threading.Lock = field(default_factory=threading.Lock) # Y-314
    _trim_count: int = 0
    _trim_log_counter: dict = field(
        default_factory=lambda: defaultdict(int)
    ) # Y-348

class L2Buffer:
    """
    L2 orderbook buffer with preallocated numpy arrays.

    Y-251: preallocated 5000 hard cap
    Y-252: searchsorted bids -price, asks price separate - O(log n) via np.searchsorted (Y-360)
    Y-253: RLock (reentrant apply_batch -> trim)
    Y-313: on_snapshot seq_epoch single increment
    Y-314: pre_sync_queue, expected_seq, _seq_lock
    Y-317a: trim sondan kes, 1000'lik blok
    Y-332: TEK SAYAC batch_bids/batch_asks birlesik sayac
    Y-344: OBI aktif len, fixed 5000 varsayimi YASAK
    Y-348: trim WARNING rate-limited (her 100 trim)
    Y-352: pre_sync_queue append eksik fix
    Y-360: np.searchsorted O(log n), list comp / for loop YASAK - bulk C-slice
    """

    MAX_BUFFER: Final[int] = 5000
    LOW_WATER: Final[int] = 4000
    TRIM_BLOCK: Final[int] = 1000
    TRIM_LOG_EVERY_N: Final[int] = 100

    def __init__(self, books: dict[str, L2Book]) -> None:
        """Books dict via DI, no global state (Y-353)."""
        self._books = books

    def get_book(self, symbol: str) -> L2Book | None:
        raise NotImplementedError("FAZ 2")

    def create_book(self, symbol: str) -> L2Book:
        raise NotImplementedError("FAZ 2")

    def apply_batch(
        self, symbol: str, diffs: list[tuple[str, float, float]], batch_epoch: int
    ) -> bool:
        """
        Apply incremental batch (Y-332, Y-318a).

        Uses np.searchsorted O(log n) for price locate (Y-360).
        Bulk C-slice for insert/delete, Python for mutation FATAL.

        Args:
            diffs: list of (side, price, qty) where side in {'bid', 'ask'}
            batch_epoch: must match seq_epoch[symbol]
        Returns:
            True if applied, False if stale epoch.
        """
        raise NotImplementedError("FAZ 2")

    def trim(self, book: L2Book, side: str, batch_new: int) -> int:
        """
        Trim farthest levels, 1000-block chunks (Y-317a, Y-348).

        Rate-limited WARNING: log every TRIM_LOG_EVERY_N calls.
        Uses bulk slice, not Python loop.
        """
        raise NotImplementedError("FAZ 2")

    def on_snapshot(self, symbol: str, snapshot: Any) -> None:
        """
        Apply snapshot, single epoch increment, pre_sync_queue clear (Y-313, Y-314).
        """
        raise NotImplementedError("FAZ 2")

    def get_obi(self, symbol: str) -> float:
        """Compute OBI aktif len (Y-344) - fixed 5000 YASAK."""
        raise NotImplementedError("FAZ 2")

    def get_obi_safe_sync(self, symbol: str) -> tuple:
        """Copy-on-read under single lock (Y-253)."""
        raise NotImplementedError("FAZ 2")

    def get_bids(self, symbol: str, depth: int = 10) -> np.ndarray:
        raise NotImplementedError("FAZ 2")

    def get_asks(self, symbol: str, depth: int = 10) -> np.ndarray:
        raise NotImplementedError("FAZ 2")