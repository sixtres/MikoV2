# YAMA Y-251..Y-360 coverage

import logging
import threading
from collections import defaultdict
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.data_layer.l2_buffer import L2Book, L2Buffer

class Snap:
    def __init__(self, bids, asks, seq):
        self.bids = bids
        self.asks = asks
        self.seq = seq
        self.bids_price = np.array([p for p, q in bids], dtype=float) if bids else np.zeros(0)
        self.bids_qty = np.array([q for p, q in bids], dtype=float) if bids else np.zeros(0)
        self.asks_price = np.array([p for p, q in asks], dtype=float) if asks else np.zeros(0)
        self.asks_qty = np.array([q for p, q in asks], dtype=float) if asks else np.zeros(0)

def _make_buffer():
    books = {}
    buf = L2Buffer(books)
    return buf, books

def test_l2book_prealloc_5000():
    book = L2Book(symbol="BTCUSDT")
    assert book.bids_price.shape == (5000,)
    assert book.asks_price.shape == (5000,)

def test_l2book_initial_len_zero():
    book = L2Book(symbol="BTCUSDT")
    assert book.bids_len == 0
    assert book.asks_len == 0

def test_create_book():
    buf, books = _make_buffer()
    b = buf.create_book("BTCUSDT")
    assert "BTCUSDT" in books
    assert b.symbol == "BTCUSDT"

def test_get_book_none():
    buf, _ = _make_buffer()
    assert buf.get_book("UNKNOWN") is None

def test_apply_batch_single_bid_insert():
    buf, _ = _make_buffer()
    buf.create_book("BTCUSDT")
    ok = buf.apply_batch("BTCUSDT", [("bid", 100.0, 1.0)], batch_epoch=0)
    assert ok is True
    book = buf.get_book("BTCUSDT")
    assert book.bids_len == 1
    assert book.bids_price[0] == 100.0

def test_apply_batch_single_ask_insert():
    buf, _ = _make_buffer()
    buf.create_book("BTCUSDT")
    ok = buf.apply_batch("BTCUSDT", [("ask", 101.0, 2.0)], batch_epoch=0)
    assert ok
    book = buf.get_book("BTCUSDT")
    assert book.asks_len == 1
    assert book.asks_price[0] == 101.0

def test_apply_batch_update_existing():
    buf, _ = _make_buffer()
    buf.create_book("BTCUSDT")
    buf.apply_batch("BTCUSDT", [("bid", 100.0, 1.0)], 0)
    buf.apply_batch("BTCUSDT", [("bid", 100.0, 5.0)], 0)
    book = buf.get_book("BTCUSDT")
    assert book.bids_len == 1
    assert book.bids_qty[0] == 5.0

def test_apply_batch_delete_qty_zero():
    buf, _ = _make_buffer()
    buf.create_book("BTCUSDT")
    buf.apply_batch("BTCUSDT", [("bid", 100.0, 1.0)], 0)
    buf.apply_batch("BTCUSDT", [("bid", 100.0, 0.0)], 0)
    book = buf.get_book("BTCUSDT")
    assert book.bids_len == 0

def test_apply_batch_epoch_mismatch_returns_false():
    buf, _ = _make_buffer()
    buf.create_book("BTCUSDT")
    ok = buf.apply_batch("BTCUSDT", [("bid", 100.0, 1.0)], batch_epoch=999)
    assert ok is False

def test_apply_batch_sorted_bids_descending():
    buf, _ = _make_buffer()
    buf.create_book("BTCUSDT")
    buf.apply_batch("BTCUSDT", [("bid", 100.0, 1.0), ("bid", 101.0, 1.0), ("bid", 99.0, 1.0)], 0)
    book = buf.get_book("BTCUSDT")
    # descending
    assert book.bids_price[0] == 101.0
    assert book.bids_price[1] == 100.0
    assert book.bids_price[2] == 99.0

def test_apply_batch_ask_ascending():
    buf, _ = _make_buffer()
    buf.create_book("BTCUSDT")
    buf.apply_batch("BTCUSDT", [("ask", 101.0, 1.0), ("ask", 100.0, 1.0), ("ask", 102.0, 1.0)], 0)
    book = buf.get_book("BTCUSDT")
    assert book.asks_price[0] == 100.0
    assert book.asks_price[1] == 101.0
    assert book.asks_price[2] == 102.0

def test_on_snapshot_epoch_increment_once():
    buf, _ = _make_buffer()
    buf.create_book("BTCUSDT")
    snap = Snap([(100.0, 1.0)], [(101.0, 1.0)], seq=10)
    buf.on_snapshot("BTCUSDT", snap)
    book = buf.get_book("BTCUSDT")
    assert book.seq_epoch["BTCUSDT"] == 1
    snap2 = Snap([(100.0, 1.0)], [(101.0, 1.0)], seq=20)
    buf.on_snapshot("BTCUSDT", snap2)
    assert book.seq_epoch["BTCUSDT"] == 2

def test_on_snapshot_truncate_over_5000():
    buf, _ = _make_buffer()
    buf.create_book("BTCUSDT")
    big_bids = [(float(i), 1.0) for i in range(6000)]
    big_asks = [(float(i), 1.0) for i in range(6000)]
    snap = Snap(big_bids, big_asks, seq=1)
    buf.on_snapshot("BTCUSDT", snap)
    book = buf.get_book("BTCUSDT")
    assert book.bids_len == 5000
    assert book.asks_len == 5000

def test_on_snapshot_pre_sync_queue_clear():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    book.pre_sync_queue["BTCUSDT"] = [
        {"seq": 5, "epoch": 0},
        {"seq": 15, "epoch": 0},
        {"seq": 25, "epoch": 1},
    ]
    # snapshot seq 10, epoch becomes 1, so only seq>10 and epoch==1 should stay
    snap = Snap([], [], seq=10)
    buf.on_snapshot("BTCUSDT", snap)
    # after epoch increment to 1, queue filtered
    assert len(book.pre_sync_queue["BTCUSDT"]) == 1
    assert book.pre_sync_queue["BTCUSDT"][0]["seq"] == 25

def test_on_snapshot_expected_seq_set():
    buf, _ = _make_buffer()
    buf.create_book("BTCUSDT")
    snap = Snap([], [], seq=100)
    buf.on_snapshot("BTCUSDT", snap)
    book = buf.get_book("BTCUSDT")
    assert book.expected_seq["BTCUSDT"] == 101

def test_trim_bids_from_end():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    # fill 4500
    for i in range(4500):
        book.bids_price[i] = float(5000 - i)
        book.bids_qty[i] = 1.0
    book.bids_len = 4500
    trimmed = buf.trim(book, "bids", batch_new=600)
    assert trimmed > 0
    assert book.bids_len < 4500
    # should trim from end, top of book preserved
    assert book.bids_price[0] == 5000.0

def test_trim_ask_from_end():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    for i in range(4500):
        book.asks_price[i] = float(i)
        book.asks_qty[i] = 1.0
    book.asks_len = 4500
    trimmed = buf.trim(book, "asks", batch_new=600)
    assert trimmed > 0
    assert book.asks_len < 4500

def test_trim_rate_limited_warning():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    with patch("src.data_layer.l2_buffer.log_warning_rate_limited") as mock_log:
        for _ in range(100):
            # reset len each time to trigger trim
            book.bids_len = 4500
            book.bids_price[:4500] = 1.0
            book.bids_qty[:4500] = 1.0
            buf.trim(book, "bids", batch_new=600)
        # every 100 should log once
        assert mock_log.call_count == 1

def test_get_obi_balanced():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    book.bids_qty[:2] = [1.0, 1.0]
    book.bids_len = 2
    book.asks_qty[:2] = [1.0, 1.0]
    book.asks_len = 2
    obi = buf.get_obi("BTCUSDT")
    assert obi == pytest.approx(0.0)

def test_get_obi_active_len_only():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    book.bids_qty[:2] = [1.0, 1.0]
    book.bids_qty[2:] = [999.0] * 4998
    book.bids_len = 2
    book.asks_qty[:2] = [1.0, 1.0]
    book.asks_len = 2
    obi = buf.get_obi("BTCUSDT")
    assert obi == pytest.approx(0.0)

def test_get_bids_depth_limit():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    for i in range(20):
        book.bids_price[i] = float(100 - i)
        book.bids_qty[i] = 1.0
    book.bids_len = 20
    bids = buf.get_bids("BTCUSDT", depth=10)
    assert len(bids) == 10

def test_get_asks_depth_limit():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    for i in range(20):
        book.asks_price[i] = float(100 + i)
        book.asks_qty[i] = 1.0
    book.asks_len = 20
    asks = buf.get_asks("BTCUSDT", depth=5)
    assert len(asks) == 5

def test_apply_batch_trim_integration():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    # fill near max
    for i in range(4990):
        book.bids_price[i] = float(5000 - i)
        book.bids_qty[i] = 1.0
    book.bids_len = 4990
    # batch adds 20 new bids, should trigger trim
    diffs = [("bid", float(i), 1.0) for i in range(20)]
    ok = buf.apply_batch("BTCUSDT", diffs, batch_epoch=0)
    assert ok
    assert book.bids_len <= 5000

def test_max_buffer_constant():
    assert L2Buffer.MAX_BUFFER == 5000
    assert L2Buffer.LOW_WATER == 4000
    assert L2Buffer.TRIM_BLOCK == 1000