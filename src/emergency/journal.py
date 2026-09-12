# YAMA Y-341: emergency_persist_state fallback journal
# YAMA Y-350: sqlite(3)->pacer(4)->flush(5)
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock

"""
EmergencyJournal - file based fallback journal for emergency persist.

Y-341: fallback when SQLite WAL direct 2s timeout fails
Y-353: DI
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True, slots=True)
class EmergencyJournalConfig:
    journal_dir: str = "var/journal"
    max_file_size_bytes: int = 10_000_000
    sync_write: bool = True

class EmergencyJournal:
    """
    Emergency journal file fallback.

    Y-341: SQLite fails -> journal append fsync
    Y-353: DI, no global
    """

    def __init__(self, config: EmergencyJournalConfig) -> None:
        self._config = config
        self._journal_path = Path(config.journal_dir) / "emergency.jsonl"
        self._lock = asyncio.Lock()

    async def append(self, symbol: str, state: dict[str, Any]) -> bool:
        """
        Append emergency state to journal file with fsync.

        Y-341: fallback journal, sync_write True
        """
        raise NotImplementedError("FAZ 4")

    async def read_all(self, symbol: str) -> list[dict[str, Any]]:
        """Read journal entries for symbol (recovery)."""
        raise NotImplementedError("FAZ 4")