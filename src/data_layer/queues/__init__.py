# YAMA Y-353: Stateless - no global mutable, DI via dependencies
# YAMA Y-357: async queue bridge - asyncio.Queue(200) + single writer

"""
Queues package.

Public API for async state and telemetry queues.
"""

from __future__ import annotations

from .async_state_queue import AsyncStateQueue
from .async_telemetry_queue import AsyncTelemetryQueue

__all__ = [
    "AsyncStateQueue",
    "AsyncTelemetryQueue",
]