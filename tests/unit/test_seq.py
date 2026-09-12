# YAMA Y-254: epoch reset on reconnect
# YAMA Y-313: seq_epoch single increment
# YAMA Y-314: per-symbol reset
# YAMA Y-358: asyncio.Lock

"""
Tests for src.data_layer.seq
"""

import asyncio

import pytest

from src.data_layer.seq import SeqState, SequenceValidator

def _make_validator():
    states: dict = {}
    locks: dict = {}
    return SequenceValidator(states, locks), states, locks

@pytest.mark.asyncio
async def test_get_state_none():
    v, _, _ = _make_validator()
    result = await v.get_state("BTCUSDT")
    assert result is None

@pytest.mark.asyncio
async def test_get_state_existing():
    v, states, locks = _make_validator()
    states["BTCUSDT"] = SeqState(last_u=100, epoch=1, last_mono_ms=1000)
    locks["BTCUSDT"] = asyncio.Lock()

    result = await v.get_state("BTCUSDT")
    assert result is not None
    assert result.last_u == 100
    assert result.epoch == 1

@pytest.mark.asyncio
async def test_validate_fresh_epoch_no_state():
    v, _, _ = _make_validator()
    res = await v.validate("BTCUSDT", epoch=1, first_u=1, final_u=10)
    assert res.needs_resync is True
    assert res.is_valid is False

@pytest.mark.asyncio
async def test_validate_epoch_mismatch():
    v, states, locks = _make_validator()
    states["BTCUSDT"] = SeqState(last_u=10, epoch=1, last_mono_ms=1000)
    locks["BTCUSDT"] = asyncio.Lock()

    res = await v.validate("BTCUSDT", epoch=2, first_u=11, final_u=20)
    assert res.needs_resync is True
    assert res.is_valid is False
    assert res.last_u == 10

@pytest.mark.asyncio
async def test_validate_stale_final_u():
    v, states, locks = _make_validator()
    states["BTCUSDT"] = SeqState(last_u=20, epoch=1, last_mono_ms=1000)
    locks["BTCUSDT"] = asyncio.Lock()

    res = await v.validate("BTCUSDT", epoch=1, first_u=5, final_u=15)
    assert res.is_valid is False
    assert res.is_gap is False
    assert res.needs_resync is False

@pytest.mark.asyncio
async def test_validate_gap_detection():
    v, states, locks = _make_validator()
    states["BTCUSDT"] = SeqState(last_u=10, epoch=1, last_mono_ms=1000)
    locks["BTCUSDT"] = asyncio.Lock()

    # first_u > last_u+1 => gap
    res = await v.validate("BTCUSDT", epoch=1, first_u=12, final_u=20)
    assert res.is_gap is True
    assert res.needs_resync is True
    assert res.is_valid is False

@pytest.mark.asyncio
async def test_validate_valid_update():
    v, states, locks = _make_validator()
    states["BTCUSDT"] = SeqState(last_u=10, epoch=1, last_mono_ms=1000)
    locks["BTCUSDT"] = asyncio.Lock()

    res = await v.validate("BTCUSDT", epoch=1, first_u=11, final_u=20)
    assert res.is_valid is True
    assert res.is_gap is False
    assert res.needs_resync is False
    assert res.last_u == 20

    # state updated
    assert states["BTCUSDT"].last_u == 20

@pytest.mark.asyncio
async def test_validate_exact_boundary():
    # off-by-one boundary: first_u == last_u+1 must be valid
    v, states, locks = _make_validator()
    states["BTCUSDT"] = SeqState(last_u=100, epoch=1, last_mono_ms=1000)
    locks["BTCUSDT"] = asyncio.Lock()

    res = await v.validate("BTCUSDT", epoch=1, first_u=101, final_u=110)
    assert res.is_valid is True
    assert res.last_u == 110

@pytest.mark.asyncio
async def test_reset_removes_state():
    v, states, locks = _make_validator()
    states["BTCUSDT"] = SeqState(last_u=10, epoch=1, last_mono_ms=1000)
    locks["BTCUSDT"] = asyncio.Lock()

    await v.reset("BTCUSDT")

    assert "BTCUSDT" not in states
    assert "BTCUSDT" not in locks

@pytest.mark.asyncio
async def test_set_epoch_creates_new_state():
    v, states, _ = _make_validator()

    await v.set_epoch("BTCUSDT", epoch=5)

    assert "BTCUSDT" in states
    assert states["BTCUSDT"].epoch == 5
    assert states["BTCUSDT"].last_u == 0

@pytest.mark.asyncio
async def test_set_epoch_resets_last_u():
    v, states, locks = _make_validator()
    states["BTCUSDT"] = SeqState(last_u=999, epoch=1, last_mono_ms=1000)
    locks["BTCUSDT"] = asyncio.Lock()

    await v.set_epoch("BTCUSDT", epoch=2)

    assert states["BTCUSDT"].last_u == 0
    assert states["BTCUSDT"].epoch == 2

@pytest.mark.asyncio
async def test_set_last_u_after_snapshot():
    v, states, locks = _make_validator()
    states["BTCUSDT"] = SeqState(last_u=0, epoch=3, last_mono_ms=1000)
    locks["BTCUSDT"] = asyncio.Lock()

    await v.set_last_u("BTCUSDT", last_u=500, mono_ms=2000)

    assert states["BTCUSDT"].last_u == 500
    assert states["BTCUSDT"].epoch == 3
    assert states["BTCUSDT"].last_mono_ms == 2000

@pytest.mark.asyncio
async def test_validate_after_epoch_change_triggers_resync():
    v, states, locks = _make_validator()
    states["BTCUSDT"] = SeqState(last_u=100, epoch=1, last_mono_ms=1000)
    locks["BTCUSDT"] = asyncio.Lock()

    await v.set_epoch("BTCUSDT", epoch=2)

    # old epoch validate should resync
    res = await v.validate("BTCUSDT", epoch=1, first_u=101, final_u=110)
    assert res.needs_resync is True
    assert res.is_valid is False

    # new epoch should be valid
    res2 = await v.validate("BTCUSDT", epoch=2, first_u=1, final_u=10)
    assert res2.is_valid is True