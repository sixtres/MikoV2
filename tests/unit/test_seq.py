# YAMA Y-254, Y-313, Y-314, Y-358
# MEXC mode tests eklendi

"""
Tests for src.data_layer.seq
"""

import asyncio

import pytest

from src.data_layer.seq import SeqMode, SeqState, SequenceValidator


def _make_validator(mode=SeqMode.BINANCE):
    states: dict = {}
    locks: dict = {}
    return SequenceValidator(states, locks, mode=mode), states, locks


# ===== Binance mode (existing, must stay passing) =====

@pytest.mark.asyncio
async def test_get_state_none():
    v, _, _ = _make_validator()
    assert await v.get_state("BTCUSDT") is None


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
    assert res.last_u == 20
    assert states["BTCUSDT"].last_u == 20


@pytest.mark.asyncio
async def test_validate_exact_boundary():
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
    assert states["BTCUSDT"].epoch == 5
    assert states["BTCUSDT"].last_u == 0


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
    res = await v.validate("BTCUSDT", epoch=1, first_u=101, final_u=110)
    assert res.needs_resync is True
    res2 = await v.validate("BTCUSDT", epoch=2, first_u=1, final_u=10)
    assert res2.is_valid is True


# ===== MEXC mode =====

@pytest.mark.asyncio
async def test_mexc_validate_first_push_after_snapshot():
    """After snapshot version V, first push must be V+1."""
    v, states, locks = _make_validator(mode=SeqMode.MEXC)
    states["BTC_USDT"] = SeqState(last_u=1000, epoch=1, last_mono_ms=1000)
    locks["BTC_USDT"] = asyncio.Lock()
    res = await v.validate("BTC_USDT", epoch=1, first_u=1001)
    assert res.is_valid is True
    assert res.last_u == 1001


@pytest.mark.asyncio
async def test_mexc_monotonic_accepts_jump():
    """MEXC throttles; version jumps are normal, not gaps."""
    v, states, locks = _make_validator(mode=SeqMode.MEXC)
    states["BTC_USDT"] = SeqState(last_u=1000, epoch=1, last_mono_ms=1000)
    locks["BTC_USDT"] = asyncio.Lock()
    res = await v.validate("BTC_USDT", epoch=1, first_u=1585)
    assert res.is_valid is True
    assert res.is_gap is False
    assert res.needs_resync is False
    assert res.last_u == 1585


@pytest.mark.asyncio
async def test_mexc_stale_version_dropped():
    """version <= last_u => stale drop, no resync."""
    v, states, locks = _make_validator(mode=SeqMode.MEXC)
    states["BTC_USDT"] = SeqState(last_u=1000, epoch=1, last_mono_ms=1000)
    locks["BTC_USDT"] = asyncio.Lock()
    res = await v.validate("BTC_USDT", epoch=1, first_u=999)
    assert res.is_valid is False
    assert res.is_gap is False
    assert res.needs_resync is False


@pytest.mark.asyncio
async def test_mexc_same_version_no_double_apply():
    """Same version applied twice => second is stale."""
    v, states, locks = _make_validator(mode=SeqMode.MEXC)
    states["BTC_USDT"] = SeqState(last_u=1000, epoch=1, last_mono_ms=1000)
    locks["BTC_USDT"] = asyncio.Lock()
    res1 = await v.validate("BTC_USDT", epoch=1, first_u=1001)
    assert res1.is_valid is True
    res2 = await v.validate("BTC_USDT", epoch=1, first_u=1001)
    assert res2.is_valid is False


@pytest.mark.asyncio
async def test_mexc_epoch_mismatch_resync():
    v, states, locks = _make_validator(mode=SeqMode.MEXC)
    states["BTC_USDT"] = SeqState(last_u=1000, epoch=1, last_mono_ms=1000)
    locks["BTC_USDT"] = asyncio.Lock()
    res = await v.validate("BTC_USDT", epoch=2, first_u=1001)
    assert res.needs_resync is True


@pytest.mark.asyncio
async def test_mexc_sequential_versions_chain():
    """Multiple sequential versions all valid."""
    v, states, locks = _make_validator(mode=SeqMode.MEXC)
    states["BTC_USDT"] = SeqState(last_u=1000, epoch=1, last_mono_ms=1000)
    locks["BTC_USDT"] = asyncio.Lock()
    for i in range(1, 11):
        res = await v.validate("BTC_USDT", epoch=1, first_u=1000 + i)
        assert res.is_valid is True, "version %d should pass" % (1000 + i)
    assert states["BTC_USDT"].last_u == 1010


@pytest.mark.asyncio
async def test_mexc_per_symbol_independent():
    v, states, locks = _make_validator(mode=SeqMode.MEXC)
    states["BTC_USDT"] = SeqState(last_u=1000, epoch=1, last_mono_ms=1000)
    states["ETH_USDT"] = SeqState(last_u=2000, epoch=1, last_mono_ms=1000)
    locks["BTC_USDT"] = asyncio.Lock()
    locks["ETH_USDT"] = asyncio.Lock()

    r1 = await v.validate("BTC_USDT", epoch=1, first_u=1001)
    r2 = await v.validate("ETH_USDT", epoch=1, first_u=2001)
    assert r1.is_valid is True
    assert r2.is_valid is True
    assert states["BTC_USDT"].last_u == 1001
    assert states["ETH_USDT"].last_u == 2001


@pytest.mark.asyncio
async def test_mexc_no_state_needs_resync():
    v, _, _ = _make_validator(mode=SeqMode.MEXC)
    res = await v.validate("BTC_USDT", epoch=1, first_u=100)
    assert res.needs_resync is True


def test_mode_default_is_binance():
    """Backward compat: default mode stays BINANCE."""
    v, _, _ = _make_validator()
    assert v.mode is SeqMode.BINANCE


def test_no_global_state():
    import src.data_layer.seq as mod
    assert not hasattr(mod, "_seq_states_global")
    assert not hasattr(mod, "_seq_locks_global")