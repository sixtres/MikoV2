# YAMA Y-263: bypass YASAK
# YAMA Y-275: rate 8 burst 15
# YAMA Y-326: async acquire
# YAMA Y-358: asyncio.Lock

"""
Tests for src.data_layer.token_bucket
"""

import asyncio
import inspect

import pytest

from src.data_layer.token_bucket import TokenBucket

def test_rate_and_burst_constants():
    assert TokenBucket.RATE == 8
    assert TokenBucket.BURST == 15

def test_init_tokens_full():
    bucket = TokenBucket()
    assert bucket.get_tokens() == 15.0

@pytest.mark.asyncio
async def test_acquire_single():
    bucket = TokenBucket()
    result = await bucket.acquire(1.0)
    assert result is True

@pytest.mark.asyncio
async def test_acquire_depletes():
    bucket = TokenBucket()
    # consume all burst
    for _ in range(15):
        await bucket.acquire(1.0)

    # 16th should need to wait ~0.125 sec (1 token / 8 rate)
    # with short timeout it should timeout
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(bucket.acquire(1.0), timeout=0.05)

@pytest.mark.asyncio
async def test_refill_after_wait():
    bucket = TokenBucket()
    for _ in range(15):
        await bucket.acquire(1.0)

    assert bucket.get_tokens() < 1.0

    await asyncio.sleep(0.3) # ~2.4 tokens refilled (0.3*8)

    tokens = bucket.get_tokens()
    assert tokens > 1.0

@pytest.mark.asyncio
async def test_acquire_multiple_tokens():
    bucket = TokenBucket()
    result = await bucket.acquire(5.0)
    assert result is True
    # 15-5 = 10 left
    assert bucket.get_tokens() == pytest.approx(10.0, abs=0.5)

@pytest.mark.asyncio
async def test_get_tokens_decreases_after_acquire():
    bucket = TokenBucket()
    before = bucket.get_tokens()
    await bucket.acquire(1.0)
    after = bucket.get_tokens()
    assert after < before

@pytest.mark.asyncio
async def test_get_tokens_caps_at_burst():
    bucket = TokenBucket()
    await bucket.acquire(5.0)
    await asyncio.sleep(2.0) # enough to refill to burst (2*8=16 >15)
    tokens = bucket.get_tokens()
    assert tokens <= 15.0
    assert tokens == pytest.approx(15.0, abs=0.01)

@pytest.mark.asyncio
async def test_acquire_waits_when_empty():
    bucket = TokenBucket()
    # empty bucket
    for _ in range(15):
        await bucket.acquire(1.0)

    # this acquire should wait, not return immediately
    start = asyncio.get_event_loop().time()
    await bucket.acquire(1.0)
    elapsed = asyncio.get_event_loop().time() - start
    # should have waited at least ~0.1 sec
    assert elapsed >= 0.1

def test_no_bypass_fatal():
    # Y-263: bypass param must not exist
    sig = inspect.signature(TokenBucket.acquire)
    params = list(sig.parameters.keys())
    assert "bypass" not in params
    assert "allow_bypass" not in params

    init_sig = inspect.signature(TokenBucket.__init__)
    init_params = list(init_sig.parameters.keys())
    assert "bypass" not in init_params