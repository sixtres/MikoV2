# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock DI

"""
Dashboard app - inline CSS critical, Chart.js /static/chart.min.js cached 1y, CDN YASAK, npm YASAK.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.sqlite_writer import SqliteWriter
    from .routes import DashboardRoutes

@dataclass(frozen=True, slots=True)
class DashboardConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    static_cache_max_age: int = 31536000  # 1y
    inline_css: bool = True

class DashboardApp:
    """
    Dashboard application.

    inline CSS critical, Chart.js /static/chart.min.js cached 1y, CDN YASAK, npm YASAK.
    Y-353: DI
    Y-358: asyncio.Lock DI
    """

    def __init__(
        self,
        config: DashboardConfig,
        routes: "DashboardRoutes",
        sqlite_writer: "SqliteWriter",
        sqlite_lock: asyncio.Lock,
    ) -> None:
        self._config = config
        self._routes = routes
        self._sqlite = sqlite_writer
        self._sqlite_lock = sqlite_lock

    async def start(self) -> None:
        """Start dashboard server."""
        raise NotImplementedError("FAZ 9")

    async def stop(self) -> None:
        """Stop dashboard server."""
        raise NotImplementedError("FAZ 9")

    def get_app(self) -> object:
        """
        Get ASGI app.

        inline CSS, /static/chart.min.js cached 1y, CDN YASAK.
        """
        raise NotImplementedError("FAZ 9")