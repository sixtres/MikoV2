# YAMA Y-260: slippage = min(0.03, 0.10/leverage)
# YAMA Y-266: task pop done_callback try/finally
# YAMA Y-311: no task leak
# YAMA Y-323: Decimal quantize str(Decimal) ROUND_DOWN
# YAMA Y-338: RuntimeError -> _direct_market_post fallback, None donus
# YAMA Y-341: emergency_persist_state ilk cagrilir
# YAMA Y-350: sqlite(3)->pacer(4)->flush(5)
# YAMA Y-351: Future pre-insert single-flight (TOCTOU fix)
# YAMA Y-353: DI

"""
Emergency close - single-flight + retry + persist-first.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..execution.flush_controller import FlushController
    from ..execution.rest_gateway import RestGateway
    from ..storage.sealed import SealedStore
    from ..storage.sqlite_writer import SqliteWriter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EmergencyCloserConfig:
    reduce_only: bool = True
    max_retry: int = 1
    leverage: int = 5
    min_lot: float = 0.001


class EmergencyCloser:
    def __init__(
        self,
        config: EmergencyCloserConfig,
        rest_gateway: "RestGateway",
        sqlite_writer: "SqliteWriter",
        sealed_store: "SealedStore",
        flush_controller: "FlushController",
        emergency_tasks: dict[str, asyncio.Task],
    ) -> None:
        self._config = config
        self._rest = rest_gateway
        self._sqlite = sqlite_writer
        self._sealed = sealed_store
        self._flush = flush_controller
        self._tasks = emergency_tasks

    def leverage_adjusted_slippage(self) -> float:
        return min(0.03, 0.10 / self._config.leverage)

    def quantize_qty(self, qty: float, precision: int) -> str:
        d = Decimal(str(qty))
        q = Decimal("1").scaleb(-precision)
        return str(d.quantize(q, rounding=ROUND_DOWN))

    async def _emergency_persist_state(self, symbol: str, payload: dict) -> None:
        try:
            await self._sqlite.execute_wal(
                {"position_id": symbol, "emergency_pending": 1}
            )
        except Exception as e:
            logger.warning("emergency persist failed symbol=%s err=%s", symbol, e)

    async def _do_close_attempt(self, symbol: str) -> str:
        """
        Tek emergency close attempt.

        Returns: CLOSED | FORCE_LIQUIDATED_BY_SYSTEM | EMERGENCY_FAILED_POSITION_OPEN
        """
        pos_qty = 1.0  # stub: get_verified_position_qty burada cagrilacak
        epsilon = self._config.min_lot / 2.0

        if abs(pos_qty) < epsilon:
            logger.warning("DUST_POSITION_REMAINING symbol=%s qty=%f", symbol, pos_qty)
            return "DUST_ACKNOWLEDGED"

        payload = {
            "symbol": symbol,
            "quantity": self.quantize_qty(abs(pos_qty), 3),
            "reduceOnly": self._config.reduce_only,
        }

        try:
            fill = await self._rest.post_market_order(payload, priority=0)
        except RuntimeError as e:
            logger.warning("pacer full fallback direct symbol=%s err=%s", symbol, e)
            try:
                result = await self._rest._direct_market_post(
                    symbol, reduce_only=self._config.reduce_only
                )
            except Exception as e2:
                logger.warning("direct market post failed symbol=%s err=%s", symbol, e2)
                return "EMERGENCY_FAILED_POSITION_OPEN"
            if result is None:
                return "EMERGENCY_FAILED_POSITION_OPEN"
            return "FORCE_LIQUIDATED_BY_SYSTEM"
        except Exception as e:
            logger.warning("post_market_order failed symbol=%s err=%s", symbol, e)
            return "EMERGENCY_FAILED_POSITION_OPEN"

        if fill is None:
            return "EMERGENCY_FAILED_POSITION_OPEN"

        # Slippage check Y-260
        slippage_pct = self.leverage_adjusted_slippage()
        fill_slippage = 0.0
        try:
            fill_slippage = float(fill.get("slippage", 0.0)) if isinstance(fill, dict) else 0.0
        except Exception:
            fill_slippage = 0.0

        if abs(fill_slippage) > slippage_pct:
            logger.warning(
                "EMERGENCY_SLIPPAGE_RETRY symbol=%s slippage=%f limit=%f",
                symbol, fill_slippage, slippage_pct,
            )
            return "FORCE_LIQUIDATED_BY_SYSTEM"

        return "CLOSED"

    async def emergency_close_with_retry(self, symbol: str) -> str:
        if symbol in self._tasks:
            try:
                return await self._tasks[symbol]
            except Exception:
                return "EMERGENCY_FAILED_POSITION_OPEN"

        async def _emergency() -> str:
            try:
                self._flush.suspend()
            except Exception as e:
                logger.warning("flush suspend failed: %s", e)

            try:
                await self._emergency_persist_state(symbol, {"phase": "start"})
                result = "EMERGENCY_FAILED_POSITION_OPEN"
                for attempt in range(self._config.max_retry + 1):
                    result = await self._do_close_attempt(symbol)
                    if result == "CLOSED":
                        break
                    if result == "FORCE_LIQUIDATED_BY_SYSTEM":
                        break
                    if result == "DUST_ACKNOWLEDGED":
                        break
                    await asyncio.sleep(0.2)
                return result
            finally:
                try:
                    self._flush.resume()
                except Exception as e:
                    logger.warning("flush resume failed: %s", e)

        task = asyncio.create_task(_emergency())
        self._tasks[symbol] = task  # Y-351 PRE-INSERT

        def _done_cb(t: asyncio.Task, sym: str = symbol) -> None:
            try:
                try:
                    exc = t.exception()
                    if exc is not None:
                        logger.warning("emergency task exc symbol=%s err=%s", sym, exc)
                except asyncio.CancelledError:
                    pass
            finally:
                self._tasks.pop(sym, None)  # Y-266 + Y-311

        task.add_done_callback(_done_cb)
        return await task