# YAMA Y-276: telemetry_queue put_nowait DROP
# YAMA Y-345: CRITICAL_ALERT + FVG_EXPIRED_HARD_DEADLINE bypass
# YAMA Y-353: stateless DI

"""
Tests for src.utils.events
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.events import CRITICAL_EVENTS, emit_event, emit_event_async

def test_critical_events_tuple():
    assert CRITICAL_EVENTS == ("CRITICAL_ALERT", "FVG_EXPIRED_HARD_DEADLINE")

def test_emit_event_critical_bypass_telemetry():
    # Y-345: CRITICAL_ALERT -> logger.warning, no telemetry
    queue = MagicMock()
    logger = MagicMock()
    payload = {"level": "critical"}

    emit_event("CRITICAL_ALERT", payload, queue, logger)

    logger.warning.assert_called_once_with("CRITICAL_ALERT", payload)
    queue.put_nowait.assert_not_called()

def test_emit_event_fvg_expired_bypass():
    # Y-345: FVG_EXPIRED_HARD_DEADLINE same bypass
    queue = MagicMock()
    logger = MagicMock()
    payload = {"fvg": "expired"}

    emit_event("FVG_EXPIRED_HARD_DEADLINE", payload, queue, logger)

    logger.warning.assert_called_once_with("FVG_EXPIRED_HARD_DEADLINE", payload)
    queue.put_nowait.assert_not_called()

def test_emit_event_normal_to_telemetry():
    # Y-276: PARTIAL_FILLED -> telemetry, no logger
    queue = MagicMock()
    logger = MagicMock()
    payload = {"qty": 1}

    emit_event("PARTIAL_FILLED", payload, queue, logger)

    logger.warning.assert_not_called()
    queue.put_nowait.assert_called_once()

def test_emit_event_normal_payload_tuple():
    queue = MagicMock()
    logger = MagicMock()
    payload = {"x": 10}

    emit_event("PARTIAL_FILLED", payload, queue, logger)

    args, _ = queue.put_nowait.call_args
    assert args[0] == ("PARTIAL_FILLED", payload)

def test_emit_event_unknown_event_to_telemetry():
    queue = MagicMock()
    logger = MagicMock()
    payload = {}

    emit_event("UNKNOWN_EVENT_XYZ", payload, queue, logger)

    logger.warning.assert_not_called()
    queue.put_nowait.assert_called_once_with(("UNKNOWN_EVENT_XYZ", payload))

def test_emit_event_telemetry_queue_is_sync():
    # Y-276: put_nowait not put
    queue = MagicMock()
    logger = MagicMock()

    emit_event("PARTIAL_FILLED", {}, queue, logger)

    assert queue.put_nowait.called
    assert not queue.put.called if hasattr(queue, "put") else True

def test_emit_event_no_return_value():
    queue = MagicMock()
    logger = MagicMock()

    result = emit_event("PARTIAL_FILLED", {}, queue, logger)
    assert result is None

    result2 = emit_event("CRITICAL_ALERT", {}, queue, logger)
    assert result2 is None

@pytest.mark.asyncio
async def test_emit_event_async_critical_alerts():
    # Y-345: async critical -> logger + alert
    queue = MagicMock()
    logger = MagicMock()
    alert = AsyncMock()
    payload = {"a": 1}

    await emit_event_async("CRITICAL_ALERT", payload, queue, logger, alert)

    logger.warning.assert_called_once_with("CRITICAL_ALERT", payload)
    alert.send_direct.assert_awaited_once_with("CRITICAL_ALERT", payload)
    queue.put_nowait.assert_not_called()

@pytest.mark.asyncio
async def test_emit_event_async_fvg_expired_alerts():
    queue = MagicMock()
    logger = MagicMock()
    alert = AsyncMock()
    payload = {"fvg": 1}

    await emit_event_async("FVG_EXPIRED_HARD_DEADLINE", payload, queue, logger, alert)

    logger.warning.assert_called_once_with("FVG_EXPIRED_HARD_DEADLINE", payload)
    alert.send_direct.assert_awaited_once_with("FVG_EXPIRED_HARD_DEADLINE", payload)
    queue.put_nowait.assert_not_called()

@pytest.mark.asyncio
async def test_emit_event_async_normal_to_telemetry():
    queue = MagicMock()
    logger = MagicMock()
    alert = AsyncMock()
    payload = {"qty": 2}

    await emit_event_async("PARTIAL_FILLED", payload, queue, logger, alert)

    logger.warning.assert_not_called()
    alert.send_direct.assert_not_called()
    queue.put_nowait.assert_called_once_with(("PARTIAL_FILLED", payload))

@pytest.mark.asyncio
async def test_emit_event_async_alerts_awaited():
    queue = MagicMock()
    logger = MagicMock()
    alert = AsyncMock()
    payload = {}

    await emit_event_async("CRITICAL_ALERT", payload, queue, logger, alert)

    # ensure awaited, not just called
    assert alert.send_direct.await_count == 1
    alert.send_direct.assert_awaited()

@pytest.mark.asyncio
async def test_emit_event_async_no_return_value():
    queue = MagicMock()
    logger = MagicMock()
    alert = AsyncMock()

    r1 = await emit_event_async("PARTIAL_FILLED", {}, queue, logger, alert)
    assert r1 is None

    r2 = await emit_event_async("CRITICAL_ALERT", {}, queue, logger, alert)
    assert r2 is None