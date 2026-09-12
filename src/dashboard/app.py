# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock DI

"""
Dashboard app - ASGI wrapper.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DashboardConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    static_cache_max_age: int = 31536000
    inline_css: bool = True


class DashboardApp:
    def __init__(
        self,
        config: DashboardConfig,
        routes: object,
        sqlite_writer: object,
        sqlite_lock: asyncio.Lock,
    ) -> None:
        self._config = config
        self._routes = routes
        self._sqlite = sqlite_writer
        self._lock = sqlite_lock
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        logger.warning("dashboard start host=%s port=%d", self._config.host, self._config.port)

    async def stop(self) -> None:
        self._started = False

    def get_app(self) -> object:
        return self._routes