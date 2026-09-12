# YAMA Y-344: OBI aktif len kullanir, fixed 5000 varsayimi YASAK
# YAMA Y-360: numpy vectorized, Python for YASAK

"""
OBI computer - active len, vectorized.

Y-344: OBI active len slice, fixed 5000 forbidden.
Y-360: numpy vectorized, Python for forbidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .l2_buffer import L2Book

@dataclass(frozen=True, slots=True)
class OBIResult:
    obi: float
    bid_volume: float
    ask_volume: float
    bid_count: int
    ask_count: int

class OBIComputer:
    def __init__(self, depth: int = 10) -> None:
        self.depth = depth

    def compute(
        self,
        bids_price,
        bids_qty,
        asks_price,
        asks_qty,
        bids_len: int,
        asks_len: int,
    ) -> OBIResult:
        """
        Compute OBI using active len.

        Y-344: active len slice [:bids_len], fixed 5000 forbidden.
        Y-360: np.sum vectorized.
        """
        # Y-344: active len respected
        bid_n = min(self.depth, bids_len)
        ask_n = min(self.depth, asks_len)

        # slice active
        bid_slice = bids_qty[:bid_n]
        ask_slice = asks_qty[:ask_n]

        # Y-360: vectorized sum
        bid_volume = float(np.sum(bid_slice)) if bid_n > 0 else 0.0
        ask_volume = float(np.sum(ask_slice)) if ask_n > 0 else 0.0

        total = bid_volume + ask_volume
        if total == 0:
            obi = 0.0
        else:
            obi = (bid_volume - ask_volume) / total

        return OBIResult(
            obi=obi,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            bid_count=bid_n,
            ask_count=ask_n,
        )

    def compute_from_book(self, book: "L2Book") -> OBIResult:
        """Compute from L2Book."""
        return self.compute(
            book.bids_price,
            book.bids_qty,
            book.asks_price,
            book.asks_qty,
            book.bids_len,
            book.asks_len,
        )

    def compute_safe(self, book: "L2Book") -> OBIResult:
        """
        Compute safe under RLock.

        Copy-on-read with lock.
        """
        with book.lock:
            return self.compute(
                book.bids_price,
                book.bids_qty,
                book.asks_price,
                book.asks_qty,
                book.bids_len,
                book.asks_len,
            )