# YAMA Y-331: funding 00/08/16 separate
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock DI

"""
Dashboard routes - SSE and health.

SSE /api/v2/sse, last_event_id replay 100, auth token, throttle normal 1000 emergency 100, per-coin %80 alive 200 else 503
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass(frozen=True, slots=True)
class RoutesConfig:
    auth_token: str = ""
    sse_throttle_normal_ms: int = 1000
    sse_throttle_emergency_ms: int = 100
    replay_buffer_size: int = 100
    alive_threshold_pct: float = 0.80

@dataclass(slots=True)
class SseEvent:
    event_id: int
    data: str
    event_type: str = "message"

class DashboardRoutes:
    """
    Dashboard routes handler.

    SSE /api/v2/sse with last_event_id replay 100, auth token validation,
    throttle normal 1000 emergency 100, per-coin %80 alive 200 else 503.
    Y-331: funding times awareness
    Y-353: DI
    Y-358: asyncio.Lock DI
    """

    def __init__(
        self,
        config: RoutesConfig,
        sqlite_lock: asyncio.Lock,
    ) -> None:
        self._config = config
        self._sqlite_lock = sqlite_lock
        self._event_buffer: list[SseEvent] = []
        self._event_id_counter: int = 0

    async def sse_stream(
        self,
        last_event_id: int | None,
        auth_token: str,
    ) -> AsyncIterator[SseEvent]:
        """
        SSE stream /api/v2/sse.

        - auth token check
        - last_event_id replay 100 events
        - throttle normal 1000ms emergency 100ms
        - per-coin %80 alive check
        """
        raise NotImplementedError("FAZ 9")
        # mypy: unreachable
        _empty: list[SseEvent] = []
        for _ev in _empty:
            yield _ev

    async def health_check(self) -> tuple[int, dict]:
        """
        Health endpoint.

        per-coin %80 alive 200 else 503.
        Returns (status_code, body)
        """
        raise NotImplementedError("FAZ 9")

    async def funding_status(self) -> dict:
        """
        Funding status endpoint.

        Y-331: 00/08/16 UTC schedule.
        """
        raise NotImplementedError("FAZ 9")

    def _validate_token(self, token: str) -> bool:
        """Validate auth token."""
        raise NotImplementedError("FAZ 9")

    def _replay_events(self, last_event_id: int) -> list[SseEvent]:
        """
        Replay events from buffer.

        last_event_id replay 100.
        """
        raise NotImplementedError("FAZ 9")