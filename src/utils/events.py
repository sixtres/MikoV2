# YAMA Y-345: CRITICAL_ALERT + FVG_EXPIRED_HARD_DEADLINE bypass telemetry_queue; emit_event sync log + emit_event_async alert
# YAMA Y-353: Stateless - telemetry_queue passed as DI parameter, no global

"""
Events utils.

Event emission with CRITICAL bypass (Y-345).
- CRITICAL_ALERT and FVG_EXPIRED_HARD_DEADLINE: logger.warning + alerting_agent.send_direct
- All other events: telemetry_queue.put_nowait
- Async variant awaits alert delivery, sync variant is fire-and-forget log
"""

from __future__ import annotations

from typing import Any, Final

CRITICAL_EVENTS: Final[tuple[str, ...]] = (
    "CRITICAL_ALERT",
    "FVG_EXPIRED_HARD_DEADLINE",
)

def emit_event(
    event_type: str, payload: dict, telemetry_queue: Any, logger: Any
) -> None:
    """
    Sync log emission (Y-345).

    CRITICAL_ALERT + FVG_EXPIRED_HARD_DEADLINE -> logger.warning only
    Others -> telemetry_queue.put_nowait((event_type, payload))
    """
    raise NotImplementedError("FAZ 1")

async def emit_event_async(
    event_type: str,
    payload: dict,
    telemetry_queue: Any,
    logger: Any,
    alerting_agent: Any,
) -> None:
    """
    Async emission with alert (Y-345).

    CRITICAL_ALERT + FVG_EXPIRED_HARD_DEADLINE -> logger.warning
    + await alerting_agent.send_direct
    Others -> telemetry_queue.put_nowait
    """
    raise NotImplementedError("FAZ 1")