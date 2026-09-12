# YAMA Y-344: OBI aktif len kullanir, fixed 5000 varsayimi YASAK
# YAMA Y-353: Stateless - no global mutable
# YAMA Y-360: numpy vectorized, Python for YASAK

"""
OBI computation.

Orderbook imbalance using active length only.
- Fixed 5000 assumption FATAL (Y-344)
- Vectorized via numpy
- Handles empty book edge - no ZeroDivisionError
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
    """
    OBI computer with active len support.

    Y-344: Uses bids_len/asks_len not 5000.
    Y-360: Vectorized sum, no Python loop.
    """

    def __init__(self, depth: int = 10) -> None:
        self._depth = depth

    def compute(
        self,
        bids_price: np.ndarray,
        bids_qty: np.ndarray,
        asks_price: np.ndarray,
        asks_qty: np.ndarray,
        bids_len: int,
        asks_len: int,
    ) -> OBIResult:
        """
        Compute OBI from active slices.

        OBI = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        bid_vol = sum(bids_qty[:min(depth, bids_len)])
        Uses vectorized numpy sum (Y-360).
        Empty book (bid_vol == ask_vol == 0): returns OBIResult(obi=0.0, ...),
        no ZeroDivisionError.
        """
        raise NotImplementedError("FAZ 2")

    def compute_from_book(self, book: "L2Book") -> OBIResult:
        """Compute from L2Book object."""
        raise NotImplementedError("FAZ 2")

    def compute_safe(self, book: "L2Book") -> OBIResult:
        """Copy-on-read safe compute under book.lock."""
        raise NotImplementedError("FAZ 2")