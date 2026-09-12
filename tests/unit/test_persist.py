import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.emergency.journal import EmergencyJournal, EmergencyJournalConfig
from src.emergency.persist import EmergencyPersist, EmergencyPersistConfig

def _make_deps(tmp_path, sqlite_ok=True, sqlite_timeout=False):
    cfg_persist = EmergencyPersistConfig(sqlite_timeout_ms=2000, journal_fallback_enabled=True)
    cfg_journal = EmergencyJournalConfig(journal_dir=str(tmp_path / "journal"), max_file_size_bytes=10_000_000, sync_write=True)
    journal = EmergencyJournal(cfg_journal)

    sqlite_writer = MagicMock()
    if sqlite_timeout:
        async def _timeout(*args, **kwargs):
            await asyncio.sleep(5)

        sqlite_writer.execute_wal = AsyncMock(side_effect=_timeout)
    else:
        if sqlite_ok:
            sqlite_writer.execute_wal = AsyncMock(return_value=None)
        else:
            sqlite_writer.execute_wal = AsyncMock(side_effect=Exception("sqlite fail"))

    persist = EmergencyPersist(cfg_persist, sqlite_writer, journal)
    return persist, sqlite_writer, journal

@pytest.mark.asyncio
async def test_emergency_persist_sqlite_success(tmp_path):
    persist, sqlite_writer, journal = _make_deps(tmp_path, sqlite_ok=True)
    ok = await persist.emergency_persist_state("BTCUSDT", {"avg": 100.0})
    assert ok is True
    sqlite_writer.execute_wal.assert_awaited()

@pytest.mark.asyncio
async def test_emergency_persist_sqlite_fail_fallback_journal(tmp_path):
    persist, sqlite_writer, journal = _make_deps(tmp_path, sqlite_ok=False)
    ok = await persist.emergency_persist_state("BTCUSDT", {"avg": 100.0})
    assert ok is True
    # journal should contain entry
    entries = await journal.read_all("BTCUSDT")
    assert len(entries) >= 1

@pytest.mark.asyncio
async def test_emergency_persist_sqlite_timeout_fallback(tmp_path):
    persist, sqlite_writer, journal = _make_deps(tmp_path, sqlite_timeout=True)
    ok = await persist.emergency_persist_state("BTCUSDT", {"avg": 100.0})
    assert ok is True
    entries = await journal.read_all("BTCUSDT")
    assert len(entries) >= 1

@pytest.mark.asyncio
async def test_emergency_persist_no_fallback_returns_false(tmp_path):
    cfg_persist = EmergencyPersistConfig(sqlite_timeout_ms=2000, journal_fallback_enabled=False)
    cfg_journal = EmergencyJournalConfig(journal_dir=str(tmp_path / "journal"))
    journal = EmergencyJournal(cfg_journal)
    sqlite_writer = MagicMock()
    sqlite_writer.execute_wal = AsyncMock(side_effect=Exception("fail"))
    persist = EmergencyPersist(cfg_persist, sqlite_writer, journal)
    ok = await persist.emergency_persist_state("BTCUSDT", {"avg": 100.0})
    assert ok is False

@pytest.mark.asyncio
async def test_emergency_persist_returns_bool(tmp_path):
    persist, _, _ = _make_deps(tmp_path, sqlite_ok=True)
    ok = await persist.emergency_persist_state("BTCUSDT", {})
    assert isinstance(ok, bool)