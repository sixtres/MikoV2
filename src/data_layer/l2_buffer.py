# YAMA Y-251: preallocated 5000 hard cap, low-water 4000
# YAMA Y-252: searchsorted bids -price, asks price AYRI
# YAMA Y-253: buffer RLock (reentrant)
# YAMA Y-308: searchsorted found flag
# YAMA Y-313: on_snapshot seq_epoch single increment
# YAMA Y-317a: trim sondan kes, 1000'lik blok, min guard
# YAMA Y-318a: apply_batch iki ayri loop (bid ve ask)
# YAMA Y-332: TEK SAYAC batch_bids/batch_asks
# YAMA Y-344: OBI aktif len
# YAMA Y-348: trim WARNING rate-limited (her 100)
# YAMA Y-352: pre_sync_queue append fix
# YAMA Y-360: np.searchsorted O(log n), list comp YASAK

"""
L2 orderbook buffer - critical file 12 yama.

Y-251: preallocated 5000 hard cap.
Y-252: searchsorted bids -price, asks price separate.
Y-253: buffer RLock reentrant.
Y-308: searchsorted found flag.
Y-313: on_snapshot seq_epoch single increment.
Y-317a: trim from end, 1000 block, min guard.
Y-318a: apply_batch two loops.
Y-332: single counter batch_bids/batch_asks.
Y-344: OBI active len.
Y-348: trim WARNING rate-limited.
Y-352: pre_sync_queue fix.
Y-360: np.searchsorted O(log n).
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..utils.logging import log_warning_rate_limited

logger = logging.getLogger(__name__)

@dataclass(slots=True)
class L2Book:
    symbol: str
    bids_price: np.ndarray = field(default_factory=lambda: np.zeros(5000, dtype=float))
    bids_qty: np.ndarray = field(default_factory=lambda: np.zeros(5000, dtype=float))
    asks_price: np.ndarray = field(default_factory=lambda: np.zeros(5000, dtype=float))
    asks_qty: np.ndarray = field(default_factory=lambda: np.zeros(5000, dtype=float))
    bids_len: int = 0
    asks_len: int = 0
    lock: threading.RLock = field(default_factory=threading.RLock)
    seq_epoch: defaultdict = field(default_factory=lambda: defaultdict(int))
    expected_seq: dict = field(default_factory=dict)
    pre_sync_queue: defaultdict = field(default_factory=lambda: defaultdict(list))
    _seq_lock: threading.Lock = field(default_factory=threading.Lock)
    _trim_count: int = 0
    _trim_log_counter: defaultdict = field(default_factory=lambda: defaultdict(int))

class L2Buffer:
    MAX_BUFFER = 5000
    LOW_WATER = 4000
    TRIM_BLOCK = 1000
    TRIM_LOG_EVERY_N = 100

    def __init__(self, books: dict[str, L2Book]) -> None:
        self.books = books

    def get_book(self, symbol: str) -> L2Book | None:
        return self.books.get(symbol)

    def create_book(self, symbol: str) -> L2Book:
        book = L2Book(symbol=symbol)
        self.books[symbol] = book
        return book

    def apply_batch(
        self,
        symbol: str,
        diffs: list[tuple[str, float, float]],
        batch_epoch: int,
    ) -> bool:
        book = self.get_book(symbol)
        if book is None:
            return False

        with book.lock:
            if batch_epoch!= book.seq_epoch[symbol]:
                return False

            batch_bids = 0
            batch_asks = 0

            # Y-318a first loop count, Y-332 single counter, Y-252 searchsorted, Y-308 found flag
            for side, price, qty in diffs:
                if qty == 0.0:
                    continue
                if side == "bid":
                    if book.bids_len > 0:
                        idx = np.searchsorted(-book.bids_price[: book.bids_len], -price)
                        found = (
                            idx < book.bids_len
                            and book.bids_price[idx] == price
                        )
                    else:
                        found = False
                    if not found:
                        batch_bids += 1
                else:
                    if book.asks_len > 0:
                        idx = np.searchsorted(book.asks_price[: book.asks_len], price)
                        found = (
                            idx < book.asks_len
                            and book.asks_price[idx] == price
                        )
                    else:
                        found = False
                    if not found:
                        batch_asks += 1

            # Y-317a trim from end
            while book.bids_len + batch_bids >= self.MAX_BUFFER:
                self.trim(book, "bids", batch_bids)
            while book.asks_len + batch_asks >= self.MAX_BUFFER:
                self.trim(book, "asks", batch_asks)

            # second loop actual apply
            for side, price, qty in diffs:
                if side == "bid":
                    if book.bids_len > 0:
                        idx = np.searchsorted(
                            -book.bids_price[: book.bids_len], -price
                        )
                        found = (
                            idx < book.bids_len
                            and book.bids_price[idx] == price
                        )
                    else:
                        idx = 0
                        found = False

                    if found:
                        if qty == 0.0:
                            if idx < book.bids_len - 1:
                                book.bids_price[idx : book.bids_len - 1] = book.bids_price[
                                    idx + 1 : book.bids_len
                                ]
                                book.bids_qty[idx : book.bids_len - 1] = book.bids_qty[
                                    idx + 1 : book.bids_len
                                ]
                            book.bids_price[book.bids_len - 1] = 0.0
                            book.bids_qty[book.bids_len - 1] = 0.0
                            book.bids_len -= 1
                        else:
                            book.bids_qty[idx] = qty
                    else:
                        if qty == 0.0:
                            continue
                        if idx < self.MAX_BUFFER:
                            if book.bids_len > 0 and idx < book.bids_len:
                                book.bids_price[idx + 1 : book.bids_len + 1] = book.bids_price[
                                    idx : book.bids_len
                                ]
                                book.bids_qty[idx + 1 : book.bids_len + 1] = book.bids_qty[
                                    idx : book.bids_len
                                ]
                            book.bids_price[idx] = price
                            book.bids_qty[idx] = qty
                            if book.bids_len < self.MAX_BUFFER:
                                book.bids_len += 1
                else:
                    if book.asks_len > 0:
                        idx = np.searchsorted(book.asks_price[: book.asks_len], price)
                        found = (
                            idx < book.asks_len
                            and book.asks_price[idx] == price
                        )
                    else:
                        idx = 0
                        found = False

                    if found:
                        if qty == 0.0:
                            if idx < book.asks_len - 1:
                                book.asks_price[idx : book.asks_len - 1] = book.asks_price[
                                    idx + 1 : book.asks_len
                                ]
                                book.asks_qty[idx : book.asks_len - 1] = book.asks_qty[
                                    idx + 1 : book.asks_len
                                ]
                            book.asks_price[book.asks_len - 1] = 0.0
                            book.asks_qty[book.asks_len - 1] = 0.0
                            book.asks_len -= 1
                        else:
                            book.asks_qty[idx] = qty
                    else:
                        if qty == 0.0:
                            continue
                        if idx < self.MAX_BUFFER:
                            if book.asks_len > 0 and idx < book.asks_len:
                                book.asks_price[idx + 1 : book.asks_len + 1] = book.asks_price[
                                    idx : book.asks_len
                                ]
                                book.asks_qty[idx + 1 : book.asks_len + 1] = book.asks_qty[
                                    idx : book.asks_len
                                ]
                            book.asks_price[idx] = price
                            book.asks_qty[idx] = qty
                            if book.asks_len < self.MAX_BUFFER:
                                book.asks_len += 1

            return True

    def trim(self, book: L2Book, side: str, batch_new: int) -> int:
        arr_len = book.bids_len if side == "bids" else book.asks_len
        trimmed = 0

        while arr_len + batch_new >= self.MAX_BUFFER:
            trim_n = min(self.TRIM_BLOCK, arr_len)
            if trim_n == 0:
                break
            if side == "bids":
                book.bids_price[arr_len - trim_n : arr_len] = 0
                book.bids_qty[arr_len - trim_n : arr_len] = 0
            else:
                book.asks_price[arr_len - trim_n : arr_len] = 0
                book.asks_qty[arr_len - trim_n : arr_len] = 0
            arr_len -= trim_n
            trimmed += trim_n

        if side == "bids":
            book.bids_len = arr_len
        else:
            book.asks_len = arr_len

        if trimmed > 0:
            book._trim_log_counter[side] += 1
            if book._trim_log_counter[side] % self.TRIM_LOG_EVERY_N == 0:
                log_warning_rate_limited(
                    logger,
                    "BUFFER_TRIM_" + side,
                    "BUFFER_TRIM count=%d trimmed=%d side=%s",
                    book._trim_log_counter[side],
                    trimmed,
                    side,
                )

        return trimmed

    def on_snapshot(self, symbol: str, snapshot: Any) -> None:
        book = self.get_book(symbol)
        if book is None:
            book = self.create_book(symbol)

        with book.lock:
            if isinstance(snapshot, dict):
                raw_bids = snapshot.get("bids", [])
                raw_asks = snapshot.get("asks", [])
                seq = snapshot.get("seq", 0)
                bids_price_arr = snapshot.get("bids_price")
                bids_qty_arr = snapshot.get("bids_qty")
                asks_price_arr = snapshot.get("asks_price")
                asks_qty_arr = snapshot.get("asks_qty")
            else:
                raw_bids = getattr(snapshot, "bids", [])
                raw_asks = getattr(snapshot, "asks", [])
                seq = getattr(snapshot, "seq", 0)
                bids_price_arr = getattr(snapshot, "bids_price", None)
                bids_qty_arr = getattr(snapshot, "bids_qty", None)
                asks_price_arr = getattr(snapshot, "asks_price", None)
                asks_qty_arr = getattr(snapshot, "asks_qty", None)

            if len(raw_bids) > self.MAX_BUFFER:
                raw_bids = raw_bids[: self.MAX_BUFFER]
            if len(raw_asks) > self.MAX_BUFFER:
                raw_asks = raw_asks[: self.MAX_BUFFER]

            book.seq_epoch[symbol] += 1

            if bids_price_arr is not None and bids_qty_arr is not None:
                n = len(raw_bids)
                book.bids_price[:n] = bids_price_arr[:n]
                book.bids_qty[:n] = bids_qty_arr[:n]
                book.bids_price[n:] = 0
                book.bids_qty[n:] = 0
                book.bids_len = n
            else:
                book.bids_price[:] = 0
                book.bids_qty[:] = 0
                for i, item in enumerate(raw_bids):
                    if isinstance(item, (list, tuple)):
                        p, q = item
                    elif isinstance(item, dict):
                        p = item.get("price", 0)
                        q = item.get("qty", 0)
                    else:
                        p = getattr(item, "price", 0)
                        q = getattr(item, "qty", 0)
                    book.bids_price[i] = p
                    book.bids_qty[i] = q
                book.bids_len = len(raw_bids)

            if asks_price_arr is not None and asks_qty_arr is not None:
                n = len(raw_asks)
                book.asks_price[:n] = asks_price_arr[:n]
                book.asks_qty[:n] = asks_qty_arr[:n]
                book.asks_price[n:] = 0
                book.asks_qty[n:] = 0
                book.asks_len = n
            else:
                book.asks_price[:] = 0
                book.asks_qty[:] = 0
                for i, item in enumerate(raw_asks):
                    if isinstance(item, (list, tuple)):
                        p, q = item
                    elif isinstance(item, dict):
                        p = item.get("price", 0)
                        q = item.get("qty", 0)
                    else:
                        p = getattr(item, "price", 0)
                        q = getattr(item, "qty", 0)
                    book.asks_price[i] = p
                    book.asks_qty[i] = q
                book.asks_len = len(raw_asks)

            book.expected_seq[symbol] = seq + 1

            with book._seq_lock:
                cur_epoch = book.seq_epoch[symbol]
                new_queue = []
                for d in book.pre_sync_queue[symbol]:
                    if isinstance(d, dict):
                        d_seq = d.get("seq", 0)
                        d_epoch = d.get("epoch", 0)
                    else:
                        d_seq = getattr(d, "seq", 0)
                        d_epoch = getattr(d, "epoch", 0)
                    if d_seq > seq and d_epoch == cur_epoch:
                        new_queue.append(d)
                book.pre_sync_queue[symbol] = new_queue

    def get_obi(self, symbol: str) -> float:
        book = self.get_book(symbol)
        if book is None:
            return 0.0
        with book.lock:
            if book.bids_len == 0 and book.asks_len == 0:
                return 0.0
            bid_vol = float(np.sum(book.bids_qty[: book.bids_len])) if book.bids_len > 0 else 0.0
            ask_vol = float(np.sum(book.asks_qty[: book.asks_len])) if book.asks_len > 0 else 0.0
            total = bid_vol + ask_vol
            if total == 0:
                return 0.0
            return (bid_vol - ask_vol) / total

    def get_obi_safe_sync(self, symbol: str) -> tuple:
        book = self.get_book(symbol)
        if book is None:
            return (np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0))
        with book.lock:
            return (
                book.bids_price[: book.bids_len].copy(),
                book.bids_qty[: book.bids_len].copy(),
                book.asks_price[: book.asks_len].copy(),
                book.asks_qty[: book.asks_len].copy(),
            )

    def get_bids(self, symbol: str, depth: int = 10) -> np.ndarray:
        book = self.get_book(symbol)
        if book is None:
            return np.zeros((0, 2))
        with book.lock:
            n = min(depth, book.bids_len)
            if n == 0:
                return np.zeros((0, 2))
            return np.column_stack(
                (book.bids_price[:n].copy(), book.bids_qty[:n].copy())
            )

    def get_asks(self, symbol: str, depth: int = 10) -> np.ndarray:
        book = self.get_book(symbol)
        if book is None:
            return np.zeros((0, 2))
        with book.lock:
            n = min(depth, book.asks_len)
            if n == 0:
                return np.zeros((0, 2))
            return np.column_stack(
                (book.asks_price[:n].copy(), book.asks_qty[:n].copy())
            )