# YAMA Y-263: bypass YASAK FATAL (critical_bypass = False)
# YAMA Y-275: TokenBucket SINGLE GLOBAL rate 8 burst 15
# YAMA Y-321a: acquire IP->symbol sira + timeout
# YAMA Y-326: await token_bucket.acquire()
# YAMA Y-338: _direct_market_post token bucket + pacer bypass only, None donus
# YAMA Y-342: sem_emergency=3 + sem_normal=9 AYRI havuz
# YAMA Y-359: single outer wait_for(3.5s), nested 4.5s YASAK
# YAMA Y-269: rest_outer_timeout_ms int (whitelist)
# YAMA Y-353: DI via __init__, no global
# YAMA Y-358: asyncio.Lock

"""
RestGateway - order execution via REST with TokenBucket and Pacer.

Y-263: critical_bypass False, bypass forbidden FATAL
Y-275: TokenBucket SINGLE GLOBAL
Y-321a: acquire IP->symbol order + timeout
Y-326: token_bucket.acquire()
Y-338: _direct_market_post token bucket + pacer bypass only
Y-342: sem_emergency 3 + sem_normal 9 separate pools
Y-359: single outer wait_for(3.5s)
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..data_layer.token_bucket import TokenBucket
    from .pacer import Pacer

@dataclass(frozen=True, slots=True)
class RestGatewayConfig:
    base_url: str
    rest_outer_timeout_ms: int = 3500 # Y-269 whitelist
    per_ip_limit: int = 15
    per_symbol_limit: int = 2
    sem_emergency_count: int = 3 # Y-342
    sem_normal_count: int = 9 # Y-342

class RestGateway:
    """
    REST gateway for order execution.

    Y-263: critical_bypass False, bypass FORBIDDEN FATAL
    Y-275: TokenBucket SINGLE GLOBAL rate 8 burst 15
    Y-321a: acquire IP->symbol order + timeout
    Y-326: await token_bucket.acquire()
    Y-338: _direct_market_post token bucket + pacer bypass only, None return
    Y-342: sem_emergency 3 + sem_normal 9 separate pools
    Y-359: single outer wait_for(3.5s), nested 4.5s FORBIDDEN
    Y-353: DI
    Y-358: asyncio.Lock
    """

    def __init__(
        self,
        config: RestGatewayConfig,
        token_bucket: "TokenBucket",
        pacer: "Pacer",
        http_client: Any, # aiohttp.ClientSession DI
    ) -> None:
        self._config = config
        self._token_bucket = token_bucket
        self._pacer = pacer
        self._client = http_client
        self._critical_bypass: bool = False # Y-263
        self._per_ip_sem: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(config.per_ip_limit)
        )
        self._per_symbol_sem: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(config.per_symbol_limit)
        )
        self._sem_emergency: asyncio.Semaphore = asyncio.Semaphore(
            config.sem_emergency_count
        ) # Y-342
        self._sem_normal: asyncio.Semaphore = asyncio.Semaphore(
            config.sem_normal_count
        ) # Y-342

    async def acquire(self, ip: str, symbol: str, is_emergency: bool = False) -> bool:
        """
        Acquire REST slot with hierarchy (Y-321a, Y-342, Y-359).

        Order: pool -> ip -> symbol -> token_bucket.
        Y-359: single outer wait_for(3.5s), nested 4.5s FORBIDDEN.
        Y-326: await token_bucket.acquire().
        Returns True if acquired, False if token bucket failed.
        """
        raise NotImplementedError("FAZ 3")

    def release(self, ip: str, symbol: str, is_emergency: bool = False) -> None:
        """Release all acquired slots in reverse order."""
        raise NotImplementedError("FAZ 3")

    async def post_market_order(self, payload: dict, priority: int = 0) -> Any:
        """
        Post market order via pacer (Y-322a).

        If pacer full (RuntimeError): CRITICAL_ALERT + _direct_market_post fallback (Y-338).
        """
        raise NotImplementedError("FAZ 3")

    async def _direct_market_post(self, symbol: str, reduce_only: bool = True) -> Any:
        """
        Emergency pacer bypass (Y-338).

        Token bucket respected, NO RAISE, returns None on failure.
        MAX_RETRY 1.
        """
        raise NotImplementedError("FAZ 3")

    async def _exchange_post(self, symbol: str, reduce_only: bool) -> Any:
        """Actual HTTP POST to exchange (aiohttp)."""
        raise NotImplementedError("FAZ 3")