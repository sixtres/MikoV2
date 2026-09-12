"""Event system for MikoV2.

Y-345: CRITICAL_ALERT events bypass telemetry queue, go directly
to alerting agent. No global state (Y-353).
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable


class EventType(Enum):
    """Event types for MikoV2."""
    
    NORMAL = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL_ALERT = auto()  # Y-345: Bypasses telemetry


@dataclass(frozen=True)
class Event:
    """Event data container.
    
    Fields:
        event_type: Type of event.
        symbol: Trading symbol (e.g., "BTCUSDT").
        message: Event message.
        timestamp_ms: Event timestamp in milliseconds.
        payload: Optional additional data.
    """
    
    event_type: EventType
    symbol: str
    message: str
    timestamp_ms: int
    payload: dict | None = None


class EventEmitter:
    """Event emitter with CRITICAL_ALERT bypass.
    
    Y-345: CRITICAL_ALERT events bypass telemetry queue and
    go directly to alerting agent.
    """
    
    def __init__(
        self,
        telemetry_callback: Callable[[Event], None],
        alerting_callback: Callable[[Event], None],
    ) -> None:
        """Initialize event emitter.
        
        Args:
            telemetry_callback: Callback for normal events.
            alerting_callback: Callback for CRITICAL_ALERT events.
        """
        self._telemetry_callback = telemetry_callback
        self._alerting_callback = alerting_callback
    
    def emit(self, event: Event) -> None:
        """Emit an event.
        
        Y-345: CRITICAL_ALERT bypasses telemetry, goes to alerting.
        
        Args:
            event: Event to emit.
        """
        if event.event_type == EventType.CRITICAL_ALERT:
            # Y-345: Bypass telemetry, go directly to alerting
            self._alerting_callback(event)
        else:
            self._telemetry_callback(event)
    
    async def emit_async(self, event: Event) -> None:
        """Emit an event asynchronously.
        
        Y-345: CRITICAL_ALERT bypasses telemetry, goes to alerting.
        
        Args:
            event: Event to emit.
        """
        if event.event_type == EventType.CRITICAL_ALERT:
            # Y-345: Bypass telemetry, go directly to alerting
            if asyncio.iscoroutinefunction(self._alerting_callback):
                await self._alerting_callback(event)
            else:
                self._alerting_callback(event)
        else:
            if asyncio.iscoroutinefunction(self._telemetry_callback):
                await self._telemetry_callback(event)
            else:
                self._telemetry_callback(event)


def create_event_emitter(
    telemetry_callback: Callable[[Event], None],
    alerting_callback: Callable[[Event], None],
) -> EventEmitter:
    """Create event emitter with callbacks.
    
    Args:
        telemetry_callback: Callback for normal events.
        alerting_callback: Callback for CRITICAL_ALERT events.
        
    Returns:
        EventEmitter: Configured emitter.
    """
    return EventEmitter(
        telemetry_callback=telemetry_callback,
        alerting_callback=alerting_callback,
    )
