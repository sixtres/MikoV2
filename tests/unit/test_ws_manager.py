# YAMA Y-254, Y-266, Y-269, Y-275, Y-311, Y-313, Y-314, Y-358

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ws_manager.manager import WSConfig, WSManager

def _make_deps():
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
    return l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks

def test_config_backoff_tuple():
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://example.com")
    assert cfg.ws_reconnect_backoff_ms == (1000, 2000, 5000, 10000, 30000)

def test_config_ping_pong_defaults():
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://example.com")
    assert cfg.ws_ping_interval_ms == 15000
    assert cfg.ws_pong_timeout_ms == 5000
    assert cfg.ws_max_ping_failures == 3

@pytest.mark.asyncio
async def test_connect_creates_task():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    await mgr.connect("BTCUSDT")
    assert "BTCUSDT" in mgr._ws_tasks
    await mgr.disconnect("BTCUSDT")

@pytest.mark.asyncio
async def test_connect_idempotent():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    await mgr.connect("BTCUSDT")
    t1 = mgr._ws_tasks["BTCUSDT"]
    await mgr.connect("BTCUSDT")
    t2 = mgr._ws_tasks["BTCUSDT"]
    assert t1 is t2
    await mgr.disconnect("BTCUSDT")

@pytest.mark.asyncio
async def test_connect_increments_epoch():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    await mgr.connect("BTCUSDT")
    e1 = mgr._current_epoch["BTCUSDT"]
    await mgr.disconnect("BTCUSDT")
    await mgr.connect("BTCUSDT")
    e2 = mgr._current_epoch["BTCUSDT"]
    assert e2 == e1 + 1
    await mgr.disconnect("BTCUSDT")

@pytest.mark.asyncio
async def test_connect_sets_epoch_in_validator():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    await mgr.connect("BTCUSDT")
    seq_validator.set_epoch.assert_awaited()
    await mgr.disconnect("BTCUSDT")

@pytest.mark.asyncio
async def test_connect_clears_pre_sync_queue():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    from src.data_layer.l2_buffer import L2Book

    book = L2Book(symbol="BTCUSDT")
    book.pre_sync_queue["BTCUSDT"] = [{"seq": 1}]
    books["BTCUSDT"] = book
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    await mgr.connect("BTCUSDT")
    assert books["BTCUSDT"].pre_sync_queue["BTCUSDT"] == []
    await mgr.disconnect("BTCUSDT")

@pytest.mark.asyncio
async def test_handle_message_stale_epoch_ignored():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    mgr._current_epoch["BTCUSDT"] = 2
    mgr._synced["BTCUSDT"] = True
    seq_validator.validate = AsyncMock(return_value=MagicMock(is_valid=True, needs_resync=False))
    await mgr.handle_message("BTCUSDT", {"seq": 10, "diffs": []}, epoch=1)
    seq_validator.validate.assert_not_awaited()

@pytest.mark.asyncio
async def test_handle_message_pre_sync_queues():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    from src.data_layer.l2_buffer import L2Book

    book = L2Book(symbol="BTCUSDT")
    books["BTCUSDT"] = book
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    mgr._current_epoch["BTCUSDT"] = 1
    mgr._synced["BTCUSDT"] = False
    await mgr.handle_message("BTCUSDT", {"seq": 10, "diffs": []}, epoch=1)
    assert len(book.pre_sync_queue["BTCUSDT"]) == 1

@pytest.mark.asyncio
async def test_handle_message_synced_validates():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    mgr._current_epoch["BTCUSDT"] = 1
    mgr._synced["BTCUSDT"] = True
    mock_result = MagicMock(is_valid=True, needs_resync=False)
    seq_validator.validate = AsyncMock(return_value=mock_result)
    await mgr.handle_message("BTCUSDT", {"seq": 10, "U": 10, "u": 10, "diffs": []}, epoch=1)
    seq_validator.validate.assert_awaited()

@pytest.mark.asyncio
async def test_handle_message_gap_triggers_resync():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    mgr._current_epoch["BTCUSDT"] = 1
    mgr._synced["BTCUSDT"] = True
    mock_result = MagicMock(is_valid=False, needs_resync=True)
    seq_validator.validate = AsyncMock(return_value=mock_result)
    mgr.resync = AsyncMock()
    await mgr.handle_message("BTCUSDT", {"seq": 10, "U": 10, "u": 11, "diffs": []}, epoch=1)
    mgr.resync.assert_awaited()

@pytest.mark.asyncio
async def test_on_snapshot_sets_synced():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    await mgr.on_snapshot("BTCUSDT", {"bids": [], "asks": []})
    assert mgr._synced["BTCUSDT"] is True

@pytest.mark.asyncio
async def test_disconnect_cancels_task():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    await mgr.connect("BTCUSDT")
    task = mgr._ws_tasks["BTCUSDT"]
    await mgr.disconnect("BTCUSDT")
    assert task.cancelled() or task.done()
    assert "BTCUSDT" not in mgr._ws_tasks

@pytest.mark.asyncio
async def test_disconnect_idempotent():
    l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks = _make_deps()
    cfg = WSConfig(symbols=("BTCUSDT",), ws_url="wss://test")
    mgr = WSManager(cfg, l2_buffer, seq_validator, token_bucket, snapshot_fetcher, books, locks)
    await mgr.disconnect("BTCUSDT")
    await mgr.disconnect("BTCUSDT")

def test_no_global_state():
    assert not hasattr(WSManager, "_ws_tasks")
    assert not hasattr(WSManager, "_current_epoch")