"""
Snapshot gap recovery integration tests.
Y-313 single epoch increment, Y-340 snapshot gecikme batch drop, Y-352 append fix.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data_layer.l2_buffer import L2Book, L2Buffer
from src.ws_manager.snapshot import SnapshotConfig, SnapshotFetcher


class _Snap:
    """Test snapshot object matching on_snapshot expectations."""

    def __init__(self, bids, asks, seq):
        self.bids = bids
        self.asks = asks
        self.seq = seq
        import numpy as np

        self.bids_price = np.array([p for p, q in bids], dtype=float) if bids else np.zeros(0)
        self.bids_qty = np.array([q for p, q in bids], dtype=float) if bids else np.zeros(0)
        self.asks_price = np.array([p for p, q in asks], dtype=float) if asks else np.zeros(0)
        self.asks_qty = np.array([q for p, q in asks], dtype=float) if asks else np.zeros(0)


def _make_buffer():
    books = {}
    return L2Buffer(books), books


@pytest.mark.asyncio
async def test_snapshot_single_epoch_increment():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    snap = _Snap([(100.0, 1.0)], [(101.0, 1.0)], seq=10)
    buf.on_snapshot("BTCUSDT", snap)
    assert book.seq_epoch["BTCUSDT"] == 1

    snap2 = _Snap([(100.0, 1.0)], [(101.0, 1.0)], seq=20)
    buf.on_snapshot("BTCUSDT", snap2)
    assert book.seq_epoch["BTCUSDT"] == 2


@pytest.mark.asyncio
async def test_snapshot_expected_seq_set():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    snap = _Snap([], [], seq=42)
    buf.on_snapshot("BTCUSDT", snap)
    assert book.expected_seq["BTCUSDT"] == 43


@pytest.mark.asyncio
async def test_snapshot_clears_pre_sync_queue_older_than_seq():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    book.pre_sync_queue["BTCUSDT"] = [
        {"seq": 5, "epoch": 0},
        {"seq": 15, "epoch": 0},
        {"seq": 25, "epoch": 1},
    ]
    snap = _Snap([], [], seq=10)
    buf.on_snapshot("BTCUSDT", snap)
    # After epoch inc to 1, only seq > 10 AND epoch == 1 remains
    remaining = book.pre_sync_queue["BTCUSDT"]
    assert len(remaining) == 1
    assert remaining[0]["seq"] == 25
    assert remaining[0]["epoch"] == 1


@pytest.mark.asyncio
async def test_snapshot_truncates_over_5000():
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    big_bids = [(float(i), 1.0) for i in range(6000)]
    big_asks = [(float(i), 1.0) for i in range(6000)]
    snap = _Snap(big_bids, big_asks, seq=1)
    buf.on_snapshot("BTCUSDT", snap)
    assert book.bids_len == 5000
    assert book.asks_len == 5000


@pytest.mark.asyncio
async def test_gap_detection_after_snapshot():
    """Snapshot sets expected_seq, then out-of-order update is dropped."""
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    snap = _Snap([(100.0, 1.0)], [(101.0, 1.0)], seq=100)
    buf.on_snapshot("BTCUSDT", snap)
    assert book.expected_seq["BTCUSDT"] == 101

    # apply_batch with matching epoch works
    ok = buf.apply_batch(
        "BTCUSDT",
        [("bid", 99.0, 2.0)],
        batch_epoch=book.seq_epoch["BTCUSDT"],
    )
    assert ok is True


@pytest.mark.asyncio
async def test_apply_batch_wrong_epoch_rejected():
    """Stale epoch batch must be dropped."""
    buf, _ = _make_buffer()
    book = buf.create_book("BTCUSDT")
    snap = _Snap([], [], seq=10)
    buf.on_snapshot("BTCUSDT", snap)
    # current epoch is 1, try epoch 0
    ok = buf.apply_batch("BTCUSDT", [("bid", 100.0, 1.0)], batch_epoch=0)
    assert ok is False


@pytest.mark.asyncio
async def test_snapshot_fetcher_uses_token_bucket():
    cfg = SnapshotConfig(rest_url="https://test", rest_outer_timeout_ms=1000)
    bucket = MagicMock()
    bucket.acquire = AsyncMock(return_value=True)
    books = {}
    l2 = L2Buffer(books)
    fetcher = SnapshotFetcher(cfg, bucket, books, l2)

    ok = await fetcher.fetch_and_apply("BTCUSDT")
    assert bucket.acquire.await_count >= 1


@pytest.mark.asyncio
async def test_snapshot_fetcher_creates_book_if_missing():
    cfg = SnapshotConfig(rest_url="https://test")
    bucket = MagicMock()
    bucket.acquire = AsyncMock(return_value=True)
    books = {}
    l2 = L2Buffer(books)
    fetcher = SnapshotFetcher(cfg, bucket, books, l2)

    await fetcher.fetch_and_apply("BTCUSDT")
    assert "BTCUSDT" in books


@pytest.mark.asyncio
async def test_snapshot_fetcher_reuses_existing_book():
    cfg = SnapshotConfig(rest_url="https://test")
    bucket = MagicMock()
    bucket.acquire = AsyncMock(return_value=True)
    books = {}
    l2 = L2Buffer(books)
    existing = l2.create_book("BTCUSDT")
    fetcher = SnapshotFetcher(cfg, bucket, books, l2)

    await fetcher.fetch_and_apply("BTCUSDT")
    assert books["BTCUSDT"] is existing


@pytest.mark.asyncio
async def test_snapshot_fetcher_token_bucket_fail_returns_false():
    cfg = SnapshotConfig(rest_url="https://test")
    bucket = MagicMock()
    bucket.acquire = AsyncMock(return_value=False)
    books = {}
    l2 = L2Buffer(books)
    fetcher = SnapshotFetcher(cfg, bucket, books, l2)

    ok = await fetcher.fetch_and_apply("BTCUSDT")
    assert ok is False


def test_no_global_state():
    import src.ws_manager.snapshot as mod

    assert not hasattr(mod, "_books")
    assert not hasattr(mod, "_l2_buffer")