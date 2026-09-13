# YAMA Y-263: critical bypass not allowed FATAL
# YAMA Y-275: token bucket acquire before request
# YAMA Y-261: global_consecutive_429, per-symbol circuit half-open 60s decay
# YAMA Y-321a: acquire IP->symbol sira + timeout
# YAMA Y-326: await token_bucket.acquire()
# YAMA Y-338: _direct_market_post token bucket + pacer bypass only, None donus
# YAMA Y-342: sem_emergency 3 + sem_normal 9 AYRI havuz
# YAMA Y-353: DI, no global
# YAMA Y-359: single outer wait_for(3.5s), nested YASAK
# YAMA Y-269: rest_outer_timeout_ms whitelist

"""
REST gateway - per-ip/per-symbol/pool semaphores + token bucket + 429 circuit.
"""

from __future__ import annotations

import asyncio
import logging
import time
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
    circuit_429_threshold: int = 3
    circuit_open_seconds: float = 60.0
    circuit_half_open_test_max: int = 1


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

        # 429 circuit state
        self._consecutive_429: dict[str, int] = defaultdict(int)
        self._circuit_open_until: dict[str, float] = {}
        self._half_open_probe_used: dict[str, bool] = defaultdict(bool)

    # --- 429 handling (Y-261) ---

    def record_429(self, symbol: str) -> None:
        """Increment 429 counter; open circuit when threshold reached."""
        self._consecutive_429[symbol] += 1
        if self._consecutive_429[symbol] >= self._config.circuit_429_threshold:
            until = time.monotonic() + self._config.circuit_open_seconds
            self._circuit_open_until[symbol] = until
            self._half_open_probe_used[symbol] = False
            logger.warning(
                "CIRCUIT_OPEN symbol=%s until_mono=%.2f count=%d",
                symbol,
                until,
                self._consecutive_429[symbol],
            )

    def record_success(self, symbol: str) -> None:
        """Reset counter and close circuit on success."""
        self._consecutive_429[symbol] = 0
        self._circuit_open_until.pop(symbol, None)
        self._half_open_probe_used[symbol] = False

    def is_circuit_open(self, symbol: str) -> bool:
        """Check circuit state (half-open allows 1 probe)."""
        until = self._circuit_open_until.get(symbol)
        if until is None:
            return False
        now = time.monotonic()
        if now >= until:
            # half-open: allow one probe
            if self._config.circuit_half_open_test_max <= 0:
                self.record_success(symbol)
                return False
            if not self._half_open_probe_used[symbol]:
                self._half_open_probe_used[symbol] = True
                logger.warning("CIRCUIT_HALF_OPEN symbol=%s", symbol)
                return False
            return True
        return True

    # --- acquire / release ---

    async def acquire(
        self, ip: str, symbol: str, is_emergency: bool = False
    ) -> bool:
        if self._critical_bypass:
            raise RuntimeError("FATAL: bypass not allowed Y-263")

        if self.is_circuit_open(symbol):
            logger.warning("CIRCUIT_BLOCK acquire symbol=%s", symbol)
            return False

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

    # --- order dispatch ---

    async def post_market_order(self, payload: dict, priority: int = 0) -> Any:
        symbol = payload.get("symbol", "")
        try:
            await self._pacer.enqueue(priority, payload)
        except RuntimeError:
            return await self._direct_market_post(symbol, reduce_only=True)

        is_emergency = priority == 0
        ok = await self.acquire("default", symbol, is_emergency=is_emergency)
        if not ok:
            return None
        try:
            result = await self._exchange_post(
                symbol, reduce_only=payload.get("reduceOnly", True)
            )
            self.record_success(symbol)
            return result
        except _RateLimited429:
            self.record_429(symbol)
            return None
        finally:
            self.release("default", symbol, is_emergency=is_emergency)

    async def _direct_market_post(
        self, symbol: str, reduce_only: bool = True
    ) -> Any:
        for attempt in (1, 2):
            ok = await self._token_bucket.acquire()
            if ok:
                try:
                    result = await self._exchange_post(symbol, reduce_only)
                    self.record_success(symbol)
                    return result
                except _RateLimited429:
                    self.record_429(symbol)
                except Exception as e:
                    logger.warning("direct market post failed: %s", e)
            await asyncio.sleep(0.5)
        logger.warning("EMERGENCY_BUCKET_EXHAUSTED symbol=%s", symbol)
        return None

    async def _exchange_post(self, symbol: str, reduce_only: bool) -> Any:
        """HTTP POST to exchange (stub for FAZ 7)."""
        return {"symbol": symbol, "reduceOnly": reduce_only, "status": "stub"}

    def set_critical_bypass(self, val: bool) -> None:
        self._critical_bypass = val


class _RateLimited429(Exception):
    """Internal marker for exchange 429 responses."""
    pass