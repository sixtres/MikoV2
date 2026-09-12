# YAMA Y-341: fallback journal
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock

"""
Emergency journal - JSONL append + fsync.

Y-341: fallback journal.
Y-353: DI.
Y-358: asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class EmergencyJournalConfig:
    journal_dir: str = "var/journal"
    max_file_size_bytes: int = 10_000_000
    sync_write: bool = True

class EmergencyJournal:
    def __init__(self, config: EmergencyJournalConfig) -> None:
        self._config = config
        self._journal_path = Path(config.journal_dir) / "emergency.jsonl"
        self._lock = asyncio.Lock()
        try:
            self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("journal mkdir failed dir=%s error=%s", config.journal_dir, e)

    async def append(self, symbol: str, state: dict) -> bool:
        entry = {"symbol": symbol, "state": state}

        def _append_sync() -> bool:
            try:
                # rotate if too large
                try:
                    if self._journal_path.exists():
                        if self._journal_path.stat().st_size > self._config.max_file_size_bytes:
                            backup = self._journal_path.with_suffix(".1.jsonl")
                            try:
                                if backup.exists():
                                    backup.unlink()
                            except Exception:
                                pass
                            try:
                                self._journal_path.rename(backup)
                                logger.warning("journal rotated size exceeded file=%s", self._journal_path)
                            except Exception as e:
                                logger.warning("journal rotate failed: %s", e)
                except Exception:
                    pass

                with open(self._journal_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
                    if self._config.sync_write:
                        f.flush()
                        try:
                            os.fsync(f.fileno())
                        except Exception as e:
                            logger.warning("fsync failed: %s", e)
                return True
            except Exception as e:
                logger.warning("journal append failed symbol=%s error=%s", symbol, e)
                return False

        async with self._lock:
            return await asyncio.to_thread(_append_sync)

    async def read_all(self, symbol: str) -> list[dict]:
        def _read_sync() -> list[dict]:
            results: list[dict] = []
            try:
                if not self._journal_path.exists():
                    return []
                with open(self._journal_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if obj.get("symbol") == symbol:
                                results.append(obj)
                        except Exception:
                            continue
            except Exception as e:
                logger.warning("journal read_all failed symbol=%s error=%s", symbol, e)
            return results

        async with self._lock:
            return await asyncio.to_thread(_read_sync)