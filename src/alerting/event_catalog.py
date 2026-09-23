# src/alerting/event_catalog.py
"""B3.4 Mod 2 — event→seviye kataloğu (R tablosu, kod içinde kilitli).

R=(C): bilinmeyen event_type sessiz INFO değil → WARNING +
"uncataloged" log satırı (fail-visible).

Seviyeler:
- CRITICAL: anında gönderim (bypass); batch'e girmez.
- WARNING: batch 5/5s.
- INFO: yalnız log + DB.

EXIT reason-aware:
    SL / TP            → WARNING
    END_OF_BACKTEST    → INFO
    diğer / None       → WARNING (fail-safe)
"""
from __future__ import annotations

import logging
from typing import Final, Optional

logger = logging.getLogger(__name__)

SEVERITY_CRITICAL: Final[str] = "CRITICAL"
SEVERITY_WARNING: Final[str] = "WARNING"
SEVERITY_INFO: Final[str] = "INFO"

SEVERITIES: Final[tuple] = (
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)

EVENT_SEVERITY: Final[dict] = {
    # CRITICAL
    "CRITICAL_ALERT": SEVERITY_CRITICAL,
    "FVG_EXPIRED_HARD_DEADLINE": SEVERITY_CRITICAL,
    "IP_BAN_DETECTED": SEVERITY_CRITICAL,
    # WARNING (EXIT reason-aware ayrı tabloda)
    "MICRO_TRIGGER_QUARANTINE": SEVERITY_WARNING,
    "FVG_INVALIDATED": SEVERITY_WARNING,
    "TRIGGER": SEVERITY_WARNING,
    "ENTRY": SEVERITY_WARNING,
    "FLIP_DETECTED": SEVERITY_WARNING,
    "TOP5_DARALMA_ALERT": SEVERITY_WARNING,
    "TRADE_REJECTED_FEE_DRAG": SEVERITY_WARNING,
    "DUST_POSITION_REMAINING": SEVERITY_WARNING,
    # INFO
    "SWEEP": SEVERITY_INFO,
    "MSS": SEVERITY_INFO,
    "FVG_OTE": SEVERITY_INFO,
    "MICRO_CONFIRM": SEVERITY_INFO,
    "ENTRY_SIGNAL": SEVERITY_INFO,
    "REJECT": SEVERITY_INFO,
    "SECOND_ENTRY_SKIPPED": SEVERITY_INFO,
    "B3_1_SUBSCRIBE": SEVERITY_INFO,
    "B3_1_UNSUBSCRIBE": SEVERITY_INFO,
}

REASON_AWARE_SEVERITY: Final[dict] = {
    "EXIT": {
        "SL": SEVERITY_WARNING,
        "TP": SEVERITY_WARNING,
        "END_OF_BACKTEST": SEVERITY_INFO,
    },
}

_EXIT_DEFAULT: Final[str] = SEVERITY_WARNING


def get_severity(
    event_type: str, reason: Optional[str] = None
) -> str:
    """event_type (ve gerekirse reason) → seviye.

    Bilinmeyen event_type → WARNING + uncataloged log (fail-visible).
    """
    if event_type in REASON_AWARE_SEVERITY:
        table = REASON_AWARE_SEVERITY[event_type]
        if reason is not None and reason in table:
            return table[reason]
        if event_type == "EXIT":
            logger.warning(
                "uncataloged reason for EXIT: %r (defaulting to %s)",
                reason,
                _EXIT_DEFAULT,
            )
            return _EXIT_DEFAULT
        logger.warning(
            "uncataloged reason for %s: %r (defaulting to WARNING)",
            event_type,
            reason,
        )
        return SEVERITY_WARNING

    if event_type in EVENT_SEVERITY:
        return EVENT_SEVERITY[event_type]

    logger.warning(
        "uncataloged event_type: %r (defaulting to WARNING)",
        event_type,
    )
    return SEVERITY_WARNING


def is_critical(
    event_type: str, reason: Optional[str] = None
) -> bool:
    """CRITICAL seviyede mi? (bypass routing kontrolü)."""
    return get_severity(event_type, reason) == SEVERITY_CRITICAL


def known_event_types() -> tuple:
    """Katalogdaki tüm event_type'ler (test/doğrulama için)."""
    return tuple(
        sorted(set(EVENT_SEVERITY) | set(REASON_AWARE_SEVERITY))
    )