import asyncio
from pathlib import Path

import pytest

from src.emergency.journal import EmergencyJournal, EmergencyJournalConfig

def _make_journal(tmp_path):
    cfg = EmergencyJournalConfig(
        journal_dir=str(tmp_path / "journal"), max_file_size_bytes=10_000_000, sync_write=True
    )
    journal = EmergencyJournal(cfg)
    return journal, cfg

def test_config_defaults():
    cfg = EmergencyJournalConfig()
    assert cfg.journal_dir == "var/journal"
    assert cfg.max_file_size_bytes == 10_000_000
    assert cfg.sync_write is True

@pytest.mark.asyncio
async def test_append_creates_file(tmp_path):
    journal, cfg = _make_journal(tmp_path)
    ok = await journal.append("BTCUSDT", {"avg": 100.0})
    assert ok is True
    assert journal._journal_path.exists()

@pytest.mark.asyncio
async def test_append_and_read_all(tmp_path):
    journal, cfg = _make_journal(tmp_path)
    await journal.append("BTCUSDT", {"avg": 100.0})
    await journal.append("BTCUSDT", {"avg": 101.0})
    await journal.append("ETHUSDT", {"avg": 200.0})
    entries = await journal.read_all("BTCUSDT")
    assert len(entries) == 2
    entries_eth = await journal.read_all("ETHUSDT")
    assert len(entries_eth) == 1

@pytest.mark.asyncio
async def test_read_all_empty(tmp_path):
    journal, cfg = _make_journal(tmp_path)
    entries = await journal.read_all("NONEXIST")
    assert entries == []

@pytest.mark.asyncio
async def test_append_fsync(tmp_path):
    journal, cfg = _make_journal(tmp_path)
    # sync_write True should not crash
    ok = await journal.append("BTCUSDT", {"x": 1})
    assert ok is True

@pytest.mark.asyncio
async def test_append_rotation(tmp_path):
    cfg = EmergencyJournalConfig(
        journal_dir=str(tmp_path / "journal"), max_file_size_bytes=10, sync_write=False
    )
    journal = EmergencyJournal(cfg)
    # write large entry to exceed limit
    await journal.append("BTCUSDT", {"data": "x" * 100})
    # next append should trigger rotate
    await journal.append("BTCUSDT", {"data": "y"})
    # backup should exist or file exists
    assert journal._journal_path.exists() or (journal._journal_path.with_suffix(".1.jsonl")).exists()

@pytest.mark.asyncio
async def test_concurrent_append(tmp_path):
    journal, cfg = _make_journal(tmp_path)

    async def _app(i):
        return await journal.append("BTCUSDT", {"i": i})

    results = await asyncio.gather(*[_app(i) for i in range(10)])
    assert all(results)
    entries = await journal.read_all("BTCUSDT")
    assert len(entries) == 10

def test_no_global_state():
    assert not hasattr(EmergencyJournal, "_journal_path") or isinstance(
        getattr(EmergencyJournal, "_journal_path", None), property
    )