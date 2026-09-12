# YAMA Y-263: critical bypass not allowed FATAL
# YAMA Y-275: token bucket acquire before request
# YAMA Y-321a: acquire IP->symbol sira + timeout
# YAMA Y-326: await token_bucket.acquire()
# YAMA Y-338: _direct_market_post token bucket + pacer bypass only, None donus
# YAMA Y-342: sem_emergency 3 + sem_normal 9 AYRI havuz
# YAMA Y-353: DI, no global
# YAMA Y-359: single outer wait_for(3.5s), nested 4.5s YASAK
# YAMA Y-269: rest_outer_timeout_ms whitelist

"""
Rest gateway - per-ip / per-symbol / pool semaphore + token bucket + outer timeout.

Y-263: critical bypass false, FATAL.
Y-275: token bucket.
Y-321a: acquire IP->symbol.
Y-326: token bucket await.
Y-338: direct market post.
Y-342: emergency 3 + normal 9 ayrı havuz.
Y-359: single outer wait_for.
Y-269: _ms whitelist.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..data_layer.token_bucket import TokenBucket
    from .pacer import Pacer

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class RestGatewayConfig:
    base_url: str = ""
    rest_outer_timeout_ms: int = 3500
    per_ip_limit: int = 15
    per_symbol_limit: int = 2
    sem_emergency_count: int = 3
    sem_normal_count: int = 9

class RestGateway:
    def __init__(
        self,
        config: RestGatewayConfig,
        token_bucket: "TokenBucket",
        pacer: "Pacer",
        http_client: Any,
    ) -> None:
        self._config = config
        self._token_bucket = token_bucket
        self._pacer = pacer
        self._client = http_client
        self._per_ip_sem: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(config.per_ip_limit)
        )
        self._per_symbol_sem: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(config.per_symbol_limit)
        )
        self._sem_emergency = asyncio.Semaphore(config.sem_emergency_count)
        self._sem_normal = asyncio.Semaphore(config.sem_normal_count)
        self._critical_bypass: bool = False

    async def acquire(
        self, ip: str, symbol: str, is_emergency: bool = False
    ) -> bool:
        if self._critical_bypass:
            raise RuntimeError("FATAL: bypass not allowed Y-263")

        ip_sem = self._per_ip_sem[ip]
        sym_sem = self._per_symbol_sem[symbol]
        pool = self._sem_emergency if is_emergency else self._sem_normal

        timeout_s = self._config.rest_outer_timeout_ms / 1000.0

        async def _do_acquire() -> None:
            await pool.acquire()
            await ip_sem.acquire()
            await sym_sem.acquire()

        try:
            await asyncio.wait_for(_do_acquire(), timeout=timeout_s)
        except asyncio.TimeoutError:
            try:
                sym_sem.release()
            except ValueError:
                pass
            try:
                ip_sem.release()
            except ValueError:
                pass
            try:
                pool.release()
            except ValueError:
                pass
            return False
        except Exception:
            return False

        ok = await self._token_bucket.acquire()
        if not ok:
            try:
                sym_sem.release()
            except ValueError:
                pass
            try:
                ip_sem.release()
            except ValueError:
                pass
            try:
                pool.release()
            except ValueError:
                pass
            return False
        return True

    def release(self, ip: str, symbol: str, is_emergency: bool = False) -> None:
        sym_sem = self._per_symbol_sem.get(symbol)
        if sym_sem is not None:
            try:
                sym_sem.release()
            except ValueError:
                pass

        ip_sem = self._per_ip_sem.get(ip)
        if ip_sem is not None:
            try:
                ip_sem.release()
            except ValueError:
                pass

        pool = self._sem_emergency if is_emergency else self._sem_normal
        try:
            pool.release()
        except ValueError:
            pass

    async def post_market_order(self, payload: dict, priority: int = 0) -> Any:
        try:
            await self._pacer.enqueue(priority, payload)
        except RuntimeError:
            return await self._direct_market_post(
                payload.get("symbol", ""), reduce_only=True
            )

        symbol = payload.get("symbol", "")
        is_emergency = priority == 0
        ok = await self.acquire("default", symbol, is_emergency=is_emergency)
        if not ok:
            return None
        try:
            return await self._exchange_post(
                symbol, reduce_only=payload.get("reduceOnly", True)
            )
        finally:
            self.release("default", symbol, is_emergency=is_emergency)

    async def _direct_market_post(
        self, symbol: str, reduce_only: bool = True
    ) -> Any:
        for attempt in (1, 2):
            ok = await self._token_bucket.acquire()
            if ok:
                try:
                    return await self._exchange_post(symbol, reduce_only)
                except Exception as e:
                    logger.warning("direct market post failed: %s", e)
            await asyncio.sleep(0.5)
        logger.warning("EMERGENCY_BUCKET_EXHAUSTED symbol=%s", symbol)
        return None

    async def _exchange_post(self, symbol: str, reduce_only: bool) -> Any:
        return {"symbol": symbol, "reduceOnly": reduce_only, "status": "stub"}

    def set_critical_bypass(self, val: bool) -> None:
        self._critical_bypass = val