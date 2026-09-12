# YAMA Y-341: SQLite WAL direct 2s timeout, fallback journal
# YAMA Y-350: sqlite(3) hierarchy
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock

"""
Emergency persist - SQLite WAL direct 2s timeout + journal fallback.

Y-341: direct 2s timeout, fallback journal.
Y-350: sqlite(3) hierarchy.
Y-353: DI.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..storage.sqlite_writer import SqliteWriter
    from .journal import EmergencyJournal

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class EmergencyPersistConfig:
    sqlite_timeout_ms: int = 2000
    journal_fallback_enabled: bool = True

class EmergencyPersist:
    def __init__(
        self,
        config: EmergencyPersistConfig,
        sqlite_writer: "SqliteWriter",
        journal: "EmergencyJournal",
    ) -> None:
        self._config = config
        self._sqlite = sqlite_writer
        self._journal = journal

    async def emergency_persist_state(self, symbol: str, state: dict) -> bool:
        payload = dict(state)
        if "symbol" not in payload:
            payload["symbol"] = symbol
        if "position_id" not in payload:
            payload["position_id"] = symbol

        timeout_s = self._config.sqlite_timeout_ms / 1000.0

        try:
            await asyncio.wait_for(
                self._sqlite.execute_wal(payload), timeout=timeout_s
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("emergency persist sqlite timeout symbol=%s", symbol)
        except Exception as e:
            logger.warning("emergency persist sqlite failed symbol=%s error=%s", symbol, e)

        if not self._config.journal_fallback_enabled:
            return False

        try:
            ok = await self._journal.append(symbol, state)
            if ok:
                logger.warning("emergency persist fallback journal ok symbol=%s", symbol)
                return True
            logger.warning("emergency persist fallback journal failed symbol=%s", symbol)
            return False
        except Exception as e:
            logger.warning("emergency persist journal exception symbol=%s error=%s", symbol, e)
            return False