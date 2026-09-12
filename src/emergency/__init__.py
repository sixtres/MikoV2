# YAMA Y-283: FLIP emergency close package
# YAMA Y-353: DI, no instance

"""
Emergency package - re-export only.

No instance creation, only re-exports for close, persist, journal.
"""

from __future__ import annotations

from .close import EmergencyCloser, EmergencyCloserConfig
from .persist import EmergencyPersist, EmergencyPersistConfig
from .journal import EmergencyJournal, EmergencyJournalConfig

__all__ = [
    "EmergencyCloser",
    "EmergencyCloserConfig",
    "EmergencyPersist",
    "EmergencyPersistConfig",
    "EmergencyJournal",
    "EmergencyJournalConfig",
]