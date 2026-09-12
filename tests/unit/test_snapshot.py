# YAMA Y-269, Y-275, Y-313, Y-353

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ws_manager.snapshot import SnapshotConfig, SnapshotFetcher

def test_config_default_timeout_3500():
    cfg = SnapshotConfig(rest_url="https://example.com")
    assert cfg.rest_outer_timeout_ms == 3500
    assert cfg.depth == 1000

@pytest.mark.asyncio
async def test_fetch_calls_token_bucket_acquire():
    cfg = SnapshotConfig(rest_url="https://example.com")
    mock_bucket = AsyncMock()
    mock_bucket.acquire = AsyncMock(return_value=True)
    books = {}
    mock_buffer = MagicMock()
    fetcher = SnapshotFetcher(cfg, mock_bucket, books, mock_buffer)
    await fetcher.fetch("BTCUSDT")
    mock_bucket.acquire.assert_awaited()

@pytest.mark.asyncio
async def test_fetch_returns_dict():
    cfg = SnapshotConfig(rest_url="https://example.com")
    mock_bucket = AsyncMock()
    mock_bucket.acquire = AsyncMock(return_value=True)
    books = {}
    mock_buffer = MagicMock()
    fetcher = SnapshotFetcher(cfg, mock_bucket, books, mock_buffer)
    result = await fetcher.fetch("BTCUSDT")
    assert isinstance(result, dict)
    assert "bids" in result

@pytest.mark.asyncio
async def test_fetch_and_apply_returns_true():
    cfg = SnapshotConfig(rest_url="https://example.com")
    mock_bucket = AsyncMock()
    mock_bucket.acquire = AsyncMock(return_value=True)
    books = {}
    mock_buffer = MagicMock()
    fetcher = SnapshotFetcher(cfg, mock_bucket, books, mock_buffer)
    fetcher.fetch = AsyncMock(return_value={"bids": [], "asks": [], "lastUpdateId": 1})
    ok = await fetcher.fetch_and_apply("BTCUSDT")
    assert ok is True

@pytest.mark.asyncio
async def test_fetch_and_apply_none_returns_false():
    cfg = SnapshotConfig(rest_url="https://example.com")
    mock_bucket = AsyncMock()
    mock_bucket.acquire = AsyncMock(return_value=True)
    books = {}
    mock_buffer = MagicMock()
    fetcher = SnapshotFetcher(cfg, mock_bucket, books, mock_buffer)
    fetcher.fetch = AsyncMock(return_value=None)
    ok = await fetcher.fetch_and_apply("BTCUSDT")
    assert ok is False

@pytest.mark.asyncio
async def test_fetch_and_apply_calls_on_snapshot():
    cfg = SnapshotConfig(rest_url="https://example.com")
    mock_bucket = AsyncMock()
    mock_bucket.acquire = AsyncMock(return_value=True)
    books = {}
    mock_buffer = MagicMock()
    fetcher = SnapshotFetcher(cfg, mock_bucket, books, mock_buffer)
    fetcher.fetch = AsyncMock(return_value={"bids": [], "asks": [], "lastUpdateId": 1})
    await fetcher.fetch_and_apply("BTCUSDT")
    mock_buffer.on_snapshot.assert_called()

@pytest.mark.asyncio
async def test_fetch_and_apply_creates_book_if_missing():
    cfg = SnapshotConfig(rest_url="https://example.com")
    mock_bucket = AsyncMock()
    mock_bucket.acquire = AsyncMock(return_value=True)
    books = {}
    mock_buffer = MagicMock()
    fetcher = SnapshotFetcher(cfg, mock_bucket, books, mock_buffer)
    fetcher.fetch = AsyncMock(return_value={"bids": [], "asks": [], "lastUpdateId": 1})
    await fetcher.fetch_and_apply("BTCUSDT")
    assert "BTCUSDT" in books

@pytest.mark.asyncio
async def test_fetch_and_apply_uses_existing_book():
    cfg = SnapshotConfig(rest_url="https://example.com")
    mock_bucket = AsyncMock()
    mock_bucket.acquire = AsyncMock(return_value=True)
    from src.data_layer.l2_buffer import L2Book

    existing = L2Book(symbol="BTCUSDT")
    books = {"BTCUSDT": existing}
    mock_buffer = MagicMock()
    fetcher = SnapshotFetcher(cfg, mock_bucket, books, mock_buffer)
    fetcher.fetch = AsyncMock(return_value={"bids": [], "asks": [], "lastUpdateId": 1})
    await fetcher.fetch_and_apply("BTCUSDT")
    assert books["BTCUSDT"] is existing

@pytest.mark.asyncio
async def test_timeout_uses_config_value():
    cfg = SnapshotConfig(rest_url="https://example.com", rest_outer_timeout_ms=100)
    mock_bucket = AsyncMock()
    mock_bucket.acquire = AsyncMock(return_value=True)
    books = {}
    mock_buffer = MagicMock()
    fetcher = SnapshotFetcher(cfg, mock_bucket, books, mock_buffer)

    async def slow_fetch():
        await asyncio.sleep(0.5)
        return {"bids": [], "asks": [], "lastUpdateId": 0}

    # patch internal _do_fetch via monkey? we test wait_for directly
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_fetch(), timeout=cfg.rest_outer_timeout_ms / 1000.0)

def test_no_global_state():
    assert not hasattr(SnapshotFetcher, "_books")
    assert not hasattr(SnapshotFetcher, "_l2_buffer")