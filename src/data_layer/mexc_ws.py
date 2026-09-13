# MEXC Futures WS depth client.
# Docs: wss://contract.mexc.com/edge
#   subscribe: {"method":"sub.depth","param":{"symbol":"BTC_USDT"}}
#   push: {"channel":"push.depth","symbol":"BTC_USDT","data":{...}}
#   ping: {"method":"ping"} every 10-15s, 60s silence = dead
# Symbol format: BTC_USDT (underscore), futures-only.

"""
MEXC Futures WS depth client (public market data, no auth).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

MEXC_WS_URL = "wss://contract.mexc.com/edge"
DEFAULT_PING_INTERVAL_S = 12.0
DEFAULT_DEAD_TIMEOUT_S = 30.0

# callback: (symbol: str, data: dict) -> None
DepthCallback = Callable[[str, dict], Awaitable[None]]


class MEXCWSClient:
    """
    Minimal MEXC Futures depth WS client.

    - subscribes to sub.depth for each symbol
    - calls on_depth(symbol, data) on every push.depth
    - sends ping every ping_interval_s
    - considers connection dead if no message in dead_timeout_s
    """

    def __init__(
        self,
        symbols: list[str],
        on_depth: DepthCallback,
        url: str = MEXC_WS_URL,
        ping_interval_s: float = DEFAULT_PING_INTERVAL_S,
        dead_timeout_s: float = DEFAULT_DEAD_TIMEOUT_S,
    ) -> None:
        self.symbols = symbols
        self.on_depth = on_depth
        self.url = url
        self.ping_interval_s = ping_interval_s
        self.dead_timeout_s = dead_timeout_s

        self._session = None
        self._ws = None
        self._read_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._last_msg_mono: float = 0.0
        self._running = False

    async def connect(self) -> None:
        import aiohttp

        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self.url, heartbeat=None)
        for sym in self.symbols:
            sub = {"method": "sub.depth", "param": {"symbol": sym}}
            await self._ws.send_json(sub)
            logger.warning("MEXC subscribed symbol=%s", sym)
        self._running = True
        self._last_msg_mono = asyncio.get_event_loop().time()
        self._read_task = asyncio.create_task(self._read_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def _read_loop(self) -> None:
        try:
            while self._running:
                msg = await self._ws.receive()
                self._last_msg_mono = asyncio.get_event_loop().time()
                if msg.type.name == "TEXT":
                    await self._handle_raw(msg.data)
                elif msg.type.name in ("CLOSE", "CLOSED", "CLOSING"):
                    logger.warning("MEXC WS closed")
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("MEXC read loop error: %s", e)

    async def _ping_loop(self) -> None:
        try:
            while self._running:
                await asyncio.sleep(self.ping_interval_s)
                now = asyncio.get_event_loop().time()
                if now - self._last_msg_mono > self.dead_timeout_s:
                    logger.warning("MEXC dead timeout exceeded")
                    break
                try:
                    await self._ws.send_json({"method": "ping"})
                except Exception as e:
                    logger.warning("MEXC ping failed: %s", e)
                    break
        except asyncio.CancelledError:
            pass

    async def _handle_raw(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except Exception:
            return
        await self._handle_message(msg)

    async def _handle_message(self, msg: dict) -> None:
        channel = msg.get("channel")
        if channel != "push.depth":
            return
        symbol = msg.get("symbol")
        data = msg.get("data")
        if not symbol or not isinstance(data, dict):
            return
        try:
            await self.on_depth(symbol, data)
        except Exception as e:
            logger.warning("MEXC on_depth failed symbol=%s err=%s", symbol, e)

    async def close(self) -> None:
        self._running = False
        for task in (self._read_task, self._ping_task):
            if task is not None and not task.done():
                task.cancel()
        for task in (self._read_task, self._ping_task):
            if task is not None:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self._read_task = None
        self._ping_task = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None