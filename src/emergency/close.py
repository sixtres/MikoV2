# YAMA Y-260: slippage = min(0.03, 0.10/leverage)
# YAMA Y-266: tasks pop done_callback try/finally
# YAMA Y-311: done_callback leak try/finally pop garanti
# YAMA Y-338: RuntimeError catch + _direct_market_post fallback, None donus
# YAMA Y-341: emergency_persist_state SQLite WAL direct 2s timeout + fallback journal
# YAMA Y-350: lock hierarchy sqlite(3)->pacer(4)->flush(5), call_soon_threadsafe YASAK direct Event
# YAMA Y-351: Future pre-insert single-flight, TOCTOU fix (if+create_task arasi await YASAK)
# YAMA Y-353: DI, no global
# YAMA Y-358: asyncio.Lock DI via flush_controller

"""
EmergencyCloser - emergency close with retry and single-flight.

Y-260: slippage = min(0.03, 0.10/leverage)
Y-266: tasks pop done_callback try/finally
Y-311: done_callback leak fix
Y-338: RuntimeError catch + _direct_market_post fallback
Y-341: emergency_persist_state SQLite WAL direct 2s + fallback journal
Y-350: sqlite(3)->pacer(4)->flush(5), call_soon_threadsafe forbidden direct Event
Y-351: Future pre-insert single-flight TOCTOU fix
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..execution.rest_gateway import RestGateway
    from ..execution.flush_controller import FlushController
    from ..storage.sqlite_writer import SqliteWriter
    from ..storage.sealed import SealedStore

@dataclass(frozen=True, slots=True)
class EmergencyCloserConfig:
    reduce_only: bool = True
    max_retry: int = 1 # Y-260 emergency_MAX_RETRY 1
    leverage: int = 5
    min_lot: float = 0.001

class EmergencyCloser:
    """
    Emergency closer - FLIP-triggered and manual reduce_only close.

    Y-260: slippage = min(0.03, 0.10/leverage)
    Y-266: tasks pop done_callback try/finally
    Y-311: done_callback leak try/finally pop garanti
    Y-338: RuntimeError catch + _direct_market_post fallback, None donus
    Y-341: emergency_persist_state SQLite WAL direct 2s timeout + fallback journal
    Y-350: lock hierarchy sqlite(3)->pacer(4)->flush(5), call_soon_threadsafe YASAK direct Event
    Y-351: Future pre-insert single-flight, TOCTOU fix (if+create_task arasi await YASAK)
    Y-353: DI
    Y-358: asyncio.Lock via flush_controller DI
    """

    def __init__(
        self,
        config: EmergencyCloserConfig,
        rest_gateway: "RestGateway",
        sqlite_writer: "SqliteWriter",
        sealed_store: "SealedStore",
        flush_controller: "FlushController",
        emergency_tasks: dict[str, asyncio.Task], # DI Y-351
    ) -> None:
        self._config = config
        self._rest = rest_gateway
        self._sqlite = sqlite_writer
        self._sealed = sealed_store
        self._flush_controller = flush_controller
        self._emergency_tasks = emergency_tasks

    async def emergency_close_with_retry(self, symbol: str) -> str:
        """
        Idempotent emergency close.

        Y-351: if symbol in _emergency_tasks -> return await (no new task)
              Future pre-insert: emergency_tasks[symbol]=task before await, TOCTOU fix
        Y-341: emergency_persist_state called first SQLite WAL direct 2s + fallback journal
        Y-260: slippage = min(0.03, 0.10/leverage) check
        Y-338: RuntimeError catch -> _direct_market_post fallback, None -> EMERGENCY_FAILED_POSITION_OPEN
        Y-350: hierarchy sqlite(3)->pacer(4)->flush(5), flush_controller suspend/resume direct Event
        Y-266/Y-311: task pop in done_callback try/finally leak fix

        Returns:
            CLOSED | DUST_ACKNOWLEDGED | FORCE_LIQUIDATED_BY_SYSTEM |
            EMERGENCY_FAILED_POSITION_OPEN
        """
        raise NotImplementedError("FAZ 4")

    def leverage_adjusted_slippage(self) -> float:
        """
        Y-260: min(0.03, 0.10/leverage).

        20x -> 0.005, 5x -> 0.02, 30x -> 0.0033
        """
        raise NotImplementedError("FAZ 4")

    def quantize_qty(self, qty: float, precision: int) -> str:
        """
        Y-323 implicit: Decimal quantize str(Decimal) ROUND_DOWN.

        str(Decimal(qty)) not Decimal(float) to avoid binary artifact.
        """
        raise NotImplementedError("FAZ 4")