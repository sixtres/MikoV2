# YAMA Y-344: active len, fixed 5000 YASAK
# YAMA Y-360: vectorized

"""
Tests for src.data_layer.obi
"""

import threading

import numpy as np
import pytest

from src.data_layer.obi import OBIComputer, OBIResult

class StubBook:
    def __init__(self, bids_qty, asks_qty):
        n_bids = len(bids_qty)
        n_asks = len(asks_qty)
        self.bids_price = np.zeros(5000)
        self.bids_qty = np.zeros(5000)
        self.asks_price = np.zeros(5000)
        self.asks_qty = np.zeros(5000)
        self.bids_qty[:n_bids] = bids_qty
        self.asks_qty[:n_asks] = asks_qty
        self.bids_price[:n_bids] = np.arange(n_bids)
        self.asks_price[:n_asks] = np.arange(n_asks)
        self.bids_len = n_bids
        self.asks_len = n_asks
        self.lock = threading.RLock()

def test_obi_balanced():
    comp = OBIComputer(depth=10)
    bids = np.array([1.0, 1.0])
    asks = np.array([1.0, 1.0])
    res = comp.compute(
        bids_price=np.zeros(5000),
        bids_qty=np.array([1.0, 1.0] + [0]*4998),
        asks_price=np.zeros(5000),
        asks_qty=np.array([1.0, 1.0] + [0]*4998),
        bids_len=2,
        asks_len=2,
    )
    assert res.obi == pytest.approx(0.0)

def test_obi_bid_heavy():
    comp = OBIComputer(depth=10)
    bids_qty = np.zeros(5000)
    asks_qty = np.zeros(5000)
    bids_qty[:2] = [3.0, 3.0]
    asks_qty[:2] = [1.0, 1.0]
    res = comp.compute(np.zeros(5000), bids_qty, np.zeros(5000), asks_qty, 2, 2)
    assert res.obi > 0
    assert res.obi == pytest.approx((6-2)/8)

def test_obi_ask_heavy():
    comp = OBIComputer(depth=10)
    bids_qty = np.zeros(5000)
    asks_qty = np.zeros(5000)
    bids_qty[:1] = [1.0]
    asks_qty[:1] = [3.0]
    res = comp.compute(np.zeros(5000), bids_qty, np.zeros(5000), asks_qty, 1, 1)
    assert res.obi < 0

def test_obi_empty_book():
    comp = OBIComputer(depth=10)
    res = comp.compute(
        np.zeros(5000), np.zeros(5000), np.zeros(5000), np.zeros(5000), 0, 0
    )
    assert res.obi == 0.0
    assert res.bid_volume == 0.0
    assert res.ask_volume == 0.0

def test_obi_only_bids():
    comp = OBIComputer(depth=10)
    bids_qty = np.zeros(5000)
    bids_qty[:3] = [1.0, 2.0, 3.0]
    res = comp.compute(np.zeros(5000), bids_qty, np.zeros(5000), np.zeros(5000), 3, 0)
    assert res.obi == pytest.approx(1.0)

def test_obi_only_asks():
    comp = OBIComputer(depth=10)
    asks_qty = np.zeros(5000)
    asks_qty[:2] = [2.0, 2.0]
    res = comp.compute(np.zeros(5000), np.zeros(5000), np.zeros(5000), asks_qty, 0, 2)
    assert res.obi == pytest.approx(-1.0)

def test_obi_depth_limit():
    comp = OBIComputer(depth=10)
    bids_qty = np.ones(5000)
    asks_qty = np.ones(5000)
    # 20 levels available but depth=10 -> only first 10 used
    res = comp.compute(np.zeros(5000), bids_qty, np.zeros(5000), asks_qty, 20, 20)
    assert res.bid_count == 10
    assert res.ask_count == 10
    assert res.bid_volume == pytest.approx(10.0)
    assert res.ask_volume == pytest.approx(10.0)

def test_obi_active_len_respected():
    comp = OBIComputer(depth=10)
    bids_qty = np.zeros(5000)
    asks_qty = np.zeros(5000)
    bids_qty[:5] = [1.0]*5
    bids_qty[5:100] = [100.0]*95 # should be ignored
    asks_qty[:5] = [1.0]*5
    asks_qty[5:100] = [100.0]*95
    res = comp.compute(np.zeros(5000), bids_qty, np.zeros(5000), asks_qty, 5, 5)
    assert res.bid_volume == pytest.approx(5.0)
    assert res.ask_volume == pytest.approx(5.0)

def test_obi_fixed_5000_forbidden():
    # Y-344: if code used fixed 5000, volume would be huge
    comp = OBIComputer(depth=10)
    bids_qty = np.zeros(5000)
    asks_qty = np.zeros(5000)
    bids_qty[:2] = [1.0, 1.0]
    bids_qty[2:] = [999.0]*4998
    res = comp.compute(np.zeros(5000), bids_qty, np.zeros(5000), asks_qty, 2, 0)
    # should only use first 2, not 5000
    assert res.bid_volume == pytest.approx(2.0)

def test_compute_from_book():
    comp = OBIComputer(depth=10)
    book = StubBook([2.0, 2.0], [1.0, 1.0])
    res = comp.compute_from_book(book)
    assert res.bid_volume == pytest.approx(4.0)
    assert res.ask_volume == pytest.approx(2.0)
    assert res.obi == pytest.approx((4-2)/6)

def test_compute_safe_under_lock():
    comp = OBIComputer(depth=10)
    book = StubBook([5.0], [5.0])
    res = comp.compute_safe(book)
    assert isinstance(res, OBIResult)
    assert res.obi == pytest.approx(0.0)

def test_obi_vectorized():
    # Y-360: ensure np.sum usage does not raise and handles large arrays
    comp = OBIComputer(depth=5000)
    bids_qty = np.ones(5000)
    asks_qty = np.ones(5000) * 2
    res = comp.compute(np.zeros(5000), bids_qty, np.zeros(5000), asks_qty, 5000, 5000)
    assert res.bid_volume == pytest.approx(5000.0)
    assert res.ask_volume == pytest.approx(10000.0)