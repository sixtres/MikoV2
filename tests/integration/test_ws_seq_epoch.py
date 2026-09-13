"""
WS sequence epoch integration tests.
Y-254 epoch reset, Y-313 single increment, Y-314 per-symbol state.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data_layer.l2_buffer import L2Book, L2Buffer
from src.data_layer.seq import SeqResult, SeqState, SequenceValidator
from src.ws_manager.manager import WSConfig, WSManager


def _make_validator():
    states = {}
    locks = {}
    return SequenceValidator(states, locks), states, locks


@pytest.mark.asyncio
async def test_seq_validator_epoch_set():
    v, _, _ = _make_validator()
    await v.set_epoch("BTCUSDT", 5)
    state = await v.get_state("BTCUSDT")
    assert state is not None
    assert state.epoch == 5
    assert state.last_u == 0


@pytest.mark.asyncio
async def test_seq_validate_first_message():
    v, _, _ = _make_validator()
    await v.set_epoch("BTCUSDT", 1)
    result = await v.validate("BTCUSDT", 1, first_u=1, final_u=10)
    assert result.is_valid is True
    assert result.last_u == 10


@pytest.mark.asyncio
async def test_seq_gap_detection():
    v, _, _ = _make_validator()
    await v.set_epoch("BTCUSDT", 1)
    await v.set_last_u("BTCUSDT", 10, 1000)
    result = await v.validate("BTCUSDT", 1, first_u=15, final_u=20)
    assert result.is_gap is True
    assert result.needs_resync is True
    assert result.is_valid is False


@pytest.mark.asyncio
async def test_seq_stale_drop():
    v, _, _ = _make_validator()
    await v.set_epoch("BTCUSDT", 1)
    await v.set_last_u("BTCUSDT", 100, 1000)
    result = await v.validate("BTCUSDT", 1, first_u=50, final_u=95)
    assert result.is_valid is False
    assert result.needs_resync is False
    assert result.is_gap is False


@pytest.mark.asyncio
async def test_seq_epoch_mismatch_needs_resync():
    v, _, _ = _make_validator()
    await v.set_epoch("BTCUSDT", 1)
    result = await v.validate("BTCUSDT", 2, first_u=1, final_u=10)
    assert result.needs_resync is True
    assert result.is_valid is False


@pytest.mark.asyncio
async def test_multi_symbol_independent_state():
    v, _, _ = _make_validator()
    await v.set_epoch("BTCUSDT", 1)
    await v.set_epoch("ETHUSDT", 1)
    await v.set_last_u("BTCUSDT", 100, 1000)
    await v.set_last_u("ETHUSDT", 200, 1000)

    btc = await v.get_state("BTCUSDT")
    eth = await v.get_state("ETHUSDT")
    assert btc.last_u == 100
    assert eth.last_u == 200


def _make_manager(l2_buffer=None):
    if l2_buffer is None:
        l2_buffer = MagicMock()
        l2_buffer.apply_batch = MagicMock(return_value=True)
        l2_buffer.on_snapshot = MagicMock()

    seq_validator = MagicMock()
    seq_validator.set_epoch = AsyncMock()
    seq_validator.validate = AsyncMock()

    token_bucket = MagicMock()
    token_bucket.acquire = AsyncMock(return_value=True)

    snapshot_fetcher = AsyncMock()
    snapshot_fetcher.fetch_and_apply = AsyncMock(return_value=True)

    books = {}
    locks = {}
    cfg = WSConfig(symbols=("BTCUSDT", "ETHUSDT"), ws_url="wss://test")
    mgr = WSManager(
        cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks
    )
    return mgr, l2_buffer, seq_validator, snapshot_fetcher, books


@pytest.mark.asyncio
async def test_ws_manager_reconnect_epoch_increment():
    mgr, _, _, _, _ = _make_manager()
    await mgr.connect("BTCUSDT")
    e1 = mgr._current_epoch["BTCUSDT"]
    await mgr.disconnect("BTCUSDT")
    await mgr.connect("BTCUSDT")
    e2 = mgr._current_epoch["BTCUSDT"]
    assert e2 == e1 + 1
    await mgr.disconnect("BTCUSDT")


@pytest.mark.asyncio
async def test_ws_manager_stale_epoch_message_dropped():
    mgr, _, seq_validator, _, _ = _make_manager()
    mgr._current_epoch["BTCUSDT"] = 2
    mgr._synced["BTCUSDT"] = True
    await mgr.handle_message("BTCUSDT", {"U": 10, "u": 20, "diffs": []}, epoch=1)
    seq_validator.validate.assert_not_awaited()


@pytest.mark.asyncio
async def test_ws_manager_pre_sync_queue_append():
    books = {}
    real_l2 = L2Buffer(books)
    book = real_l2.create_book("BTCUSDT")

    mgr, _, _, _, _ = _make_manager(l2_buffer=real_l2)
    mgr._books["BTCUSDT"] = book
    mgr._current_epoch["BTCUSDT"] = 1
    mgr._synced["BTCUSDT"] = False

    await mgr.handle_message("BTCUSDT", {"seq": 42, "diffs": []}, epoch=1)
    assert len(book.pre_sync_queue["BTCUSDT"]) == 1
    assert book.pre_sync_queue["BTCUSDT"][0]["seq"] == 42
    assert book.pre_sync_queue["BTCUSDT"][0]["epoch"] == 1


@pytest.mark.asyncio
async def test_ws_manager_pre_sync_queue_cleared_on_connect():
    books = {}
    real_l2 = L2Buffer(books)
    book = real_l2.create_book("BTCUSDT")
    book.pre_sync_queue["BTCUSDT"] = [{"seq": 1, "epoch": 0}]

    mgr, _, _, _, _ = _make_manager(l2_buffer=real_l2)
    mgr._books["BTCUSDT"] = book

    await mgr.connect("BTCUSDT")
    assert book.pre_sync_queue["BTCUSDT"] == []
    await mgr.disconnect("BTCUSDT")


@pytest.mark.asyncio
async def test_seq_gap_then_resync_flow():
    v, _, _ = _make_validator()
    await v.set_epoch("BTCUSDT", 1)
    await v.set_last_u("BTCUSDT", 10, 1000)

    # gap: first_u 15 > last_u 10 + 1
    result = await v.validate("BTCUSDT", 1, first_u=15, final_u=20)
    assert result.needs_resync is True

    # resync: reset + set_epoch to new epoch
    await v.reset("BTCUSDT")
    await v.set_epoch("BTCUSDT", 2)
    state = await v.get_state("BTCUSDT")
    assert state.epoch == 2
    assert state.last_u == 0

    # new epoch valid
    result2 = await v.validate("BTCUSDT", 2, first_u=1, final_u=10)
    assert result2.is_valid is True


def test_no_global_state():
    import src.ws_manager.manager as mod

    assert not hasattr(mod, "_current_epoch")
    assert not hasattr(mod, "_synced")