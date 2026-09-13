# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock DI
# REV7: aiohttp.web server

"""
Dashboard app - aiohttp.web server.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiohttp import web

if TYPE_CHECKING:
    from .routes import DashboardRoutes

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DashboardConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    static_cache_max_age: int = 31536000
    inline_css: bool = True
    static_dir: str = "src/dashboard/static"
    index_file: str = "src/dashboard/static/index.html"


class DashboardApp:
    def __init__(
        self,
        config: DashboardConfig,
        routes: "DashboardRoutes",
        sqlite_writer: Any,
        sqlite_lock: asyncio.Lock,
    ) -> None:
        self._config = config
        self._routes = routes
        self._sqlite = sqlite_writer
        self._lock = sqlite_lock
        self._started = False
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        if self._started:
            return
        self._app = web.Application()
        self._setup_routes()
        self._runner = web.AppRunner(self._app, shutdown_timeout=2.0)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner, self._config.host, self._config.port
        )
        await self._site.start()
        self._started = True
        logger.warning(
            "dashboard start host=%s port=%d",
            self._config.host,
            self._config.port,
        )

    async def stop(self) -> None:
        if not self._started:
            return
        if self._site is not None:
            try:
                await self._site.stop()
            except Exception as e:
                logger.warning("site stop failed: %s", e)
            self._site = None
        if self._runner is not None:
            try:
                await self._runner.cleanup()
            except Exception as e:
                logger.warning("runner cleanup failed: %s", e)
            self._runner = None
        self._app = None
        self._started = False

    def get_app(self) -> web.Application | None:
        return self._app

    # --------------------------------------------------------------- routing

    def _setup_routes(self) -> None:
        assert self._app is not None
        self._app.router.add_get("/", self._handle_index)
        self._app.router.add_get("/api/v2/health", self._handle_health)
        self._app.router.add_get("/api/v2/positions", self._handle_positions)
        self._app.router.add_get("/api/v2/whales", self._handle_whales)
        self._app.router.add_get("/api/v2/equity", self._handle_equity)
        self._app.router.add_get("/api/v2/pnl", self._handle_pnl)
        self._app.router.add_get("/api/v2/metrics", self._handle_metrics)
        self._app.router.add_get("/api/v2/sse", self._handle_sse)

        static_path = Path(self._config.static_dir)
        if static_path.is_dir():
            self._app.router.add_static(
                "/static/", path=str(static_path), name="static"
            )

    # --------------------------------------------------------------- handlers

    async def _handle_index(self, request: web.Request) -> web.Response:
        index_path = Path(self._config.index_file)
        if index_path.is_file():
            return web.FileResponse(str(index_path))
        return web.Response(
            text="<h1>MikoV2 dashboard</h1><p>index.html not found</p>",
            content_type="text/html",
        )

    async def _handle_health(self, request: web.Request) -> web.Response:
        status, body = await self._routes.health()
        return web.json_response(body, status=status)

    async def _handle_positions(self, request: web.Request) -> web.Response:
        try:
            limit = int(request.query.get("limit", "100"))
        except ValueError:
            limit = 100
        body = await self._routes.positions(limit=limit)
        return web.json_response(body)

    async def _handle_whales(self, request: web.Request) -> web.Response:
        try:
            limit = int(request.query.get("limit", "50"))
        except ValueError:
            limit = 50
        body = await self._routes.whales(limit=limit)
        return web.json_response(body)

    async def _handle_equity(self, request: web.Request) -> web.Response:
        body = await self._routes.equity()
        return web.json_response(body)

    async def _handle_pnl(self, request: web.Request) -> web.Response:
        body = await self._routes.pnl()
        return web.json_response(body)

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        body = await self._routes.metrics()
        return web.json_response(body)

    async def _handle_sse(self, request: web.Request) -> web.StreamResponse:
        auth_token = request.query.get("token", "")
        last_id_raw = request.query.get("last_event_id")
        last_id: int | None = None
        if last_id_raw is not None:
            try:
                last_id = int(last_id_raw)
            except ValueError:
                last_id = None

        resp = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        await resp.prepare(request)

        try:
            async for ev in self._routes.sse_stream(last_id, auth_token):
                chunk = self._format_sse(ev)
                await resp.write(chunk.encode("utf-8"))
        except PermissionError:
            return resp
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("sse stream error: %s", e)
        finally:
            try:
                await resp.write_eof()
            except Exception:
                pass
        return resp

    @staticmethod
    def _format_sse(ev: dict) -> str:
        out = []
        if "id" in ev:
            out.append("id: %s" % ev["id"])
        if "event" in ev:
            out.append("event: %s" % ev["event"])
        data = ev.get("data", "")
        if isinstance(data, (dict, list)):
            data = json.dumps(data)
        out.append("data: %s" % data)
        out.append("")
        out.append("")
        return "\n".join(out)