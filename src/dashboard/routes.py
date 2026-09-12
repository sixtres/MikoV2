# YAMA Y-269: _ms int whitelist
# YAMA Y-345: SSE auth token
# YAMA Y-353: DI, no global
# YAMA Y-358: asyncio.Lock DI

"""
Dashboard routes - SSE stream, health, funding status.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import AsyncIterator

logger = logging.getLogger(__name__)


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
    def __init__(self, config: RoutesConfig, sqlite_lock: asyncio.Lock) -> None:
        self._config = config
        self._lock = sqlite_lock
        self._event_buffer: list[SseEvent] = []
        self._event_id_counter: int = 0

    def _validate_token(self, token: str) -> bool:
        expected = self._config.auth_token
        if not expected:
            return True
        return token == expected

    def _replay_events(self, last_event_id: int) -> list[SseEvent]:
        limit = self._config.replay_buffer_size
        out: list[SseEvent] = []
        for ev in self._event_buffer:
            if ev.event_id > last_event_id:
                out.append(ev)
                if len(out) >= limit:
                    break
        return out

    async def sse_stream(
        self, last_event_id: int | None, auth_token: str
    ) -> AsyncIterator[SseEvent]:
        if not self._validate_token(auth_token):
            logger.warning("sse_stream auth failed")
            raise PermissionError("invalid token")

        if last_event_id is not None:
            for ev in self._replay_events(last_event_id):
                yield ev

        self._event_id_counter += 1
        dummy = SseEvent(
            event_id=self._event_id_counter,
            data='{"status":"ok"}',
            event_type="message",
        )
        yield dummy

    async def health_check(self) -> tuple[int, dict]:
        try:
            alive = 1.0
            if alive < self._config.alive_threshold_pct:
                return 503, {"status": "unhealthy", "alive_pct": alive}
            return 200, {"status": "ok", "alive_pct": alive}
        except Exception as e:
            logger.warning("health_check failed: %s", e)
            return 503, {"status": "error"}

    async def funding_status(self) -> dict:
        times = (0, 8, 16)
        return {"times": list(times), "next": 8}