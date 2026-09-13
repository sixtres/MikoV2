"""
Mock-based shadow smoke test (CI-friendly).
Real SequenceValidator + L2Buffer; mocked MEXC REST + WS push handler.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data_layer.l2_buffer import L2Buffer
from src.data_layer.obi import OBIComputer
from src.data_layer.seq import SeqMode, SequenceValidator


def _mk_book(buffer, symbol, bids, asks):
    book = buffer.create_book(symbol)
    import numpy as np

    for i, (p, q) in enumerate(bids):
        book.bids_price[i] = p
        book.bids_qty[i] = q
    book.bids_len = len(bids)
    for i, (p, q) in enumerate(asks):
        book.asks_price[i] = p
        book.asks_qty[i] = q
    book.asks_len = len(asks)
    return book


def _apply_diffs(buffer, symbol, diffs):
    book = buffer.get_book(symbol)
    return buffer.apply_batch(
        symbol, diffs, batch_epoch=book.seq_epoch.get(symbol, 0)
    )


@pytest.mark.asyncio
async def test_shadow_snapshot_then_stream():
    symbol = "BTC_USDT"
    books = {}
    buffer = L2Buffer(books)
    seq = SequenceValidator({}, {}, mode=SeqMode.MEXC)

    # Bootstrap snapshot version=1000
    _mk_book(buffer, symbol, [(99.0, 1.0), (98.0, 2.0)], [(101.0, 1.0), (102.0, 2.0)])
    await seq.set_epoch(symbol, 1)
    await seq.set_last_u(symbol, 1000, 0)

    # Three sequential pushes
    for i, (bid, qty) in enumerate([(99.5, 3.0), (99.0, 5.0), (98.5, 1.0)]):
        version = 1001 + i
        result = await seq.validate(symbol, 1, first_u=version)
        assert result.is_valid is True
        _apply_diffs(buffer, symbol, [("bid", bid, qty)])

    book = buffer.get_book(symbol)
    assert book.bids_len >= 1
    obi_val = buffer.get_obi(symbol)
    assert -1.0 <= obi_val <= 1.0


@pytest.mark.asyncio
async def test_shadow_stale_drop_and_monotonic_accept():
    """
    MEXC mode: jump is not gap (throttle); only regression is stale.
    """
    symbol = "BTC_USDT"
    books = {}
    buffer = L2Buffer(books)
    seq = SequenceValidator({}, {}, mode=SeqMode.MEXC)

    _mk_book(buffer, symbol, [(99.0, 1.0)], [(101.0, 1.0)])
    await seq.set_epoch(symbol, 1)
    await seq.set_last_u(symbol, 500, 0)

    # jump from 500 to 505 -> accepted (MEXC throttles versions)
    res = await seq.validate(symbol, 1, first_u=505)
    assert res.is_valid is True
    assert res.needs_resync is False

    # regression 504 -> 503 stale, dropped
    res2 = await seq.validate(symbol, 1, first_u=503)
    assert res2.is_valid is False
    assert res2.needs_resync is False


@pytest.mark.asyncio
async def test_shadow_stale_dropped():
    symbol = "BTC_USDT"
    books = {}
    buffer = L2Buffer(books)
    seq = SequenceValidator({}, {}, mode=SeqMode.MEXC)

    _mk_book(buffer, symbol, [(99.0, 1.0)], [(101.0, 1.0)])
    await seq.set_epoch(symbol, 1)
    await seq.set_last_u(symbol, 100, 0)

    r = await seq.validate(symbol, 1, first_u=99)
    assert r.is_valid is False
    assert r.is_gap is False
    assert r.needs_resync is False


@pytest.mark.asyncio
async def test_shadow_obi_calculation_increases_on_bid_heavy_flow():
    symbol = "BTC_USDT"
    books = {}
    buffer = L2Buffer(books)
    seq = SequenceValidator({}, {}, mode=SeqMode.MEXC)
    obi = OBIComputer(depth=5)

    _mk_book(buffer, symbol, [(99.0, 1.0)], [(101.0, 1.0)])
    await seq.set_epoch(symbol, 1)
    await seq.set_last_u(symbol, 100, 0)

    obi_before = buffer.get_obi(symbol)

    # Bid-heavy updates
    for i in range(5):
        version = 101 + i
        await seq.validate(symbol, 1, first_u=version)
        _apply_diffs(buffer, symbol, [("bid", 99.0 - i * 0.1, 100.0)])

    obi_after = buffer.get_obi(symbol)
    assert obi_after > obi_before


def test_shadow_no_global_state():
    import src.data_layer.mexc_ws as ws_mod
    import src.data_layer.mexc_rest as rest_mod

    assert not hasattr(ws_mod.MEXCWSClient, "_session")
    assert not hasattr(rest_mod.MEXCRestClient, "_session")