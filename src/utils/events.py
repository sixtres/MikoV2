# YAMA Y-276: telemetry_queue put_nowait DROP (sadece telemetry)
# YAMA Y-345: CRITICAL_ALERT + FVG_EXPIRED_HARD_DEADLINE bypass telemetry_queue; sync=log only, async=alert
# YAMA Y-353: stateless, DI parameters (no global)

"""
Event emitter - critical bypass.

Y-345: CRITICAL_ALERT + FVG_EXPIRED_HARD_DEADLINE bypass telemetry_queue.
Y-276: telemetry_queue put_nowait only.
Y-353: stateless utils, DI via parameters.
"""

from __future__ import annotations

from typing import Any, Final

CRITICAL_EVENTS: Final[tuple[str,...]] = ("CRITICAL_ALERT", "FVG_EXPIRED_HARD_DEADLINE")

def emit_event(
    event_type: str,
    payload: dict,
    telemetry_queue: Any,
    logger: Any,
) -> None:
    """
    Sync emit.

    - critical -> logger.warning, bypass telemetry (Y-345)
    - normal -> telemetry_queue.put_nowait((event_type, payload)) (Y-276)
    """
    if event_type in CRITICAL_EVENTS:
        logger.warning(event_type, payload)
        return

    telemetry_queue.put_nowait((event_type, payload))

async def emit_event_async(
    event_type: str,
    payload: dict,
    telemetry_queue: Any,
    logger: Any,
    alerting_agent: Any,
) -> None:
    """
    Async emit.

    - critical -> logger.warning + await alerting_agent.send_direct (Y-345)
    - normal -> telemetry_queue.put_nowait((event_type, payload))
    """
    if event_type in CRITICAL_EVENTS:
        logger.warning(event_type, payload)
        await alerting_agent.send_direct(event_type, payload)
        return

    telemetry_queue.put_nowait((event_type, payload))