# src/alerting/migration.py
"""Tek migration bloğu — B3.4 Y=(D)+S=(D)+V=(C)+H+AF+AG+AJ.

Kapsam:
- alert_events (5-durumlu delivery_status: pending/sending/delivered/
  failed/expired; AF=(C) SENDING ZORUNLU, AB4 optimistic lock için)
- micro_trigger_events (H)
- Index (delivery_status, ts_ms) + (symbol, ts_ms) (sorgu desenleri)
- Ek index (ts_ms) — retention DELETE için
- PRAGMA user_version ile idempotent migration kontrolü
- rowid alt-sorgu chunked DELETE (AJ — portable; build opsiyonuna
  bağlı değil)

Kısıtlar (Z=(C)):
- Bu modül hiçbir ağ çağrısı yapmaz; txn açık tutmaz. Caller migration
  sonrası tek commit eder.
- Migration fail-fast raise; sessiz yutma YASAK.
- Tek migration fonksiyonu (parçalı YASAK).
"""
from __future__ import annotations

import sqlite3
from typing import Final

SCHEMA_VERSION: Final[int] = 1

DELIVERY_STATUSES: Final[tuple] = (
    "pending",
    "sending",
    "delivered",
    "failed",
    "expired",
)

MICRO_TRIGGER_RETENTION_MS: Final[int] = 3 * 24 * 3600 * 1000
ALERT_EVENTS_RETENTION_MS: Final[int] = 7 * 24 * 3600 * 1000

_ALLOWED_TABLES: Final[frozenset] = frozenset(
    {"alert_events", "micro_trigger_events"}
)

_DDL_ALERT_EVENTS: Final[str] = """
CREATE TABLE IF NOT EXISTS alert_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    symbol TEXT,
    payload TEXT,
    delivery_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (delivery_status IN
               ('pending','sending','delivered','failed','expired')),
    correlation_id TEXT,
    source_seq INTEGER,
    exchange_ts_ms INTEGER,
    created_at_ms INTEGER NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
)
"""

_DDL_MICRO_TRIGGER_EVENTS: Final[str] = """
CREATE TABLE IF NOT EXISTS micro_trigger_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    event_type TEXT NOT NULL,
    state_from TEXT,
    state_to TEXT,
    payload TEXT,
    correlation_id TEXT,
    source_seq INTEGER,
    exchange_ts_ms INTEGER
)
"""

_DDL_INDEXES: Final[tuple] = (
    "CREATE INDEX IF NOT EXISTS idx_alert_events_status_ts "
    "ON alert_events(delivery_status, ts_ms)",
    "CREATE INDEX IF NOT EXISTS idx_alert_events_ts "
    "ON alert_events(ts_ms)",
    "CREATE INDEX IF NOT EXISTS idx_micro_trigger_symbol_ts "
    "ON micro_trigger_events(symbol, ts_ms)",
    "CREATE INDEX IF NOT EXISTS idx_micro_trigger_ts "
    "ON micro_trigger_events(ts_ms)",
)


def run_migration(conn: sqlite3.Connection) -> int:
    """Idempotent migration — PRAGMA user_version ile korunur.

    Dönüş: migration sonrası user_version (SCHEMA_VERSION).
    Hata: sqlite3.Error raise (fail-fast; çağıran rollback eder).
    """
    cur = conn.cursor()
    row = cur.execute("PRAGMA user_version").fetchone()
    current = int(row[0]) if row else 0
    if current >= SCHEMA_VERSION:
        return current

    try:
        cur.execute(_DDL_ALERT_EVENTS)
        cur.execute(_DDL_MICRO_TRIGGER_EVENTS)
        for ddl in _DDL_INDEXES:
            cur.execute(ddl)
        cur.execute("PRAGMA user_version = {}".format(SCHEMA_VERSION))
        conn.commit()
    except sqlite3.Error:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        raise
    return SCHEMA_VERSION


def chunked_delete_older_than(
    conn: sqlite3.Connection,
    table: str,
    cutoff_ms: int,
    chunk: int = 5000,
) -> int:
    """AJ=(C) — rowid alt-sorgu; DELETE ... LIMIT build opsiyonuna bağlı
    değil (portable). Silinen toplam satır sayısını döner.

    tablo adı whitelist ile sınırlı (SQL injection'a karşı).
    chunk 1..50000 aralığında; dışı raise.
    """
    if table not in _ALLOWED_TABLES:
        raise ValueError(
            "chunked_delete_older_than: unknown table {!r}".format(table)
        )
    if not isinstance(chunk, int) or chunk <= 0 or chunk > 50000:
        raise ValueError("chunked_delete_older_than: chunk out of range")

    sql = (
        "DELETE FROM {table} WHERE id IN "
        "(SELECT id FROM {table} WHERE ts_ms < ? LIMIT ?)"
    ).format(table=table)

    total = 0
    cur = conn.cursor()
    while True:
        cur.execute(sql, (cutoff_ms, chunk))
        n = cur.rowcount
        if n <= 0:
            break
        total += n
    conn.commit()
    return total