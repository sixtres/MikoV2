# src/alerting/__init__.py
"""MikoV2 alerting package — B3.4 Mod 2.

T1 kapsamı: migration entry point + kanonik şema sabitleri.
Agent / formatter / event_catalog sonraki teslimlerde eklenir.
"""
from .migration import (
    SCHEMA_VERSION,
    DELIVERY_STATUSES,
    MICRO_TRIGGER_RETENTION_MS,
    ALERT_EVENTS_RETENTION_MS,
    run_migration,
    chunked_delete_older_than,
)

__all__ = [
    "SCHEMA_VERSION",
    "DELIVERY_STATUSES",
    "MICRO_TRIGGER_RETENTION_MS",
    "ALERT_EVENTS_RETENTION_MS",
    "run_migration",
    "chunked_delete_older_than",
]