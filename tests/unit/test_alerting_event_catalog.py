# tests/unit/test_alerting_event_catalog.py
"""B3.4 Mod 2 — event_catalog R tablosu test matrisi (T2)."""
from __future__ import annotations

import logging

import pytest

from src.alerting.event_catalog import (
    EVENT_SEVERITY,
    REASON_AWARE_SEVERITY,
    SEVERITIES,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    get_severity,
    is_critical,
    known_event_types,
)


@pytest.mark.parametrize("event_type", [
    "CRITICAL_ALERT",
    "FVG_EXPIRED_HARD_DEADLINE",
    "IP_BAN_DETECTED",
])
def test_critical_events(event_type):
    assert get_severity(event_type) == SEVERITY_CRITICAL
    assert is_critical(event_type) is True


@pytest.mark.parametrize("event_type", [
    "MICRO_TRIGGER_QUARANTINE",
    "FVG_INVALIDATED",
    "TRIGGER",
    "ENTRY",
    "FLIP_DETECTED",
    "TOP5_DARALMA_ALERT",
    "TRADE_REJECTED_FEE_DRAG",
    "DUST_POSITION_REMAINING",
    # B3.5-AC=A: inert mode transition simetrisi (Q2=B).
    "OBSERVATION_STOPPED",
    "OBSERVATION_RESUMED",
    # B3.5-AE=A: auto-finalize milestone.
    "OBSERVATION_COMPLETED",
])
def test_warning_events(event_type):
    assert get_severity(event_type) == SEVERITY_WARNING
    assert is_critical(event_type) is False


@pytest.mark.parametrize("event_type", [
    "SWEEP",
    "MSS",
    "FVG_OTE",
    "MICRO_CONFIRM",
    "ENTRY_SIGNAL",
    "REJECT",
    "SECOND_ENTRY_SKIPPED",
    "B3_1_SUBSCRIBE",
    "B3_1_UNSUBSCRIBE",
])
def test_info_events(event_type):
    assert get_severity(event_type) == SEVERITY_INFO
    assert is_critical(event_type) is False


def test_exit_reason_sl_warning():
    assert get_severity("EXIT", reason="SL") == SEVERITY_WARNING


def test_exit_reason_tp_warning():
    assert get_severity("EXIT", reason="TP") == SEVERITY_WARNING


def test_exit_reason_end_of_backtest_info():
    assert get_severity(
        "EXIT", reason="END_OF_BACKTEST"
    ) == SEVERITY_INFO


def test_exit_unknown_reason_defaults_warning(caplog):
    with caplog.at_level(logging.WARNING):
        sev = get_severity("EXIT", reason="WAT")
    assert sev == SEVERITY_WARNING
    assert any(
        "uncataloged" in r.message for r in caplog.records
    )


def test_unknown_event_type_defaults_warning(caplog):
    with caplog.at_level(logging.WARNING):
        sev = get_severity("TOTALLY_UNKNOWN_XYZ")
    assert sev == SEVERITY_WARNING
    assert any(
        "uncataloged" in r.message for r in caplog.records
    )


def test_known_event_types_contains_all():
    known = set(known_event_types())
    expected = {
        "CRITICAL_ALERT",
        "FVG_EXPIRED_HARD_DEADLINE",
        "IP_BAN_DETECTED",
        "MICRO_TRIGGER_QUARANTINE",
        "FVG_INVALIDATED",
        "TRIGGER",
        "ENTRY",
        "EXIT",
        "FLIP_DETECTED",
        "TOP5_DARALMA_ALERT",
        "TRADE_REJECTED_FEE_DRAG",
        "DUST_POSITION_REMAINING",
        "SWEEP",
        "MSS",
        "FVG_OTE",
        "MICRO_CONFIRM",
        "ENTRY_SIGNAL",
        "REJECT",
        "SECOND_ENTRY_SKIPPED",
        "B3_1_SUBSCRIBE",
        "B3_1_UNSUBSCRIBE",
    }
    assert expected.issubset(known)


def test_severities_tuple():
    assert SEVERITIES == (
        SEVERITY_CRITICAL,
        SEVERITY_WARNING,
        SEVERITY_INFO,
    )


def test_reason_aware_only_exit():
    assert set(REASON_AWARE_SEVERITY) == {"EXIT"}


def test_event_severity_table_no_reason_aware_leak():
    # EXIT, reason-aware tabloda; EVENT_SEVERITY'ye sızmamalı.
    assert "EXIT" not in EVENT_SEVERITY