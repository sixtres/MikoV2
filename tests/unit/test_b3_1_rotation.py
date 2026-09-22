# tests/unit/test_b3_1_rotation.py
"""B3.1 rotation: hysteresis + flap (round-trip) + quarantine + stable reset.

Q1=B (1h pencere), Q2=B (round-trip), Q3=B (7 gün stabil reset),
Q5=A (watch state yok). Kilitli DURUM §11 B3.1 A-G.
"""

from __future__ import annotations

import pytest

from src.data_layer.universe_service import (
    UniverseService,
    ScanResult,
    DEFAULT_HYSTERESIS_MS,
    DEFAULT_FLAP_THRESHOLD,
    DEFAULT_QUARANTINE_RESET_STABLE_MS,
)
from src.data_layer.metrics_fetcher import FetcherConfig


def _svc(always_include: tuple[str, ...] = ()) -> UniverseService:
    return UniverseService(
        rest=None,                      # apply_scan için REST gerekmez
        fetcher_config=FetcherConfig(),
        contract_sizes={},
        always_include=always_include,
    )


def _scan(top5, top10=None, top20=None) -> ScanResult:
    top5 = list(top5)
    top10 = list(top10) if top10 is not None else list(top5)
    top20 = list(top20) if top20 is not None else list(top10)
    return ScanResult(
        top5=top5, top10=top10, top20=top20,
        ranked=[], excluded_symbols=[],
    )


T0 = 1_700_000_000_000
H = DEFAULT_HYSTERESIS_MS


def test_seed_filters_excluded_and_is_idempotent():
    svc = _svc()
    svc._excluded = frozenset({"XAUT_USDT"})
    svc.seed_subscriptions(["BTC_USDT", "XAUT_USDT"])
    assert svc.current_subscriptions() == frozenset({"BTC_USDT"})
    svc.seed_subscriptions(["BTC_USDT"])
    assert svc.current_subscriptions() == frozenset({"BTC_USDT"})


def test_hysteresis_blocks_early_subscribe():
    svc = _svc()
    svc.apply_scan(_scan(["BTC_USDT"]), T0)
    d = svc.apply_scan(_scan(["BTC_USDT"]), T0 + 1000)
    assert d.to_subscribe == ()
    assert svc.current_subscriptions() == frozenset()


def test_hysteresis_completes_subscribe():
    svc = _svc()
    svc.apply_scan(_scan(["BTC_USDT"]), T0)
    d = svc.apply_scan(_scan(["BTC_USDT"]), T0 + H + 1)
    assert d.to_subscribe == ("BTC_USDT",)
    assert "BTC_USDT" in svc.current_subscriptions()


def test_round_trip_counts_one_flap():
    """Q2=B: Top5 gir-çık = 1 flap birimi."""
    svc = _svc()
    svc.apply_scan(_scan(["BTC_USDT"]), T0)
    svc.apply_scan(_scan(["BTC_USDT"]), T0 + H + 1)
    assert "BTC_USDT" in svc.current_subscriptions()
    # BTC Top5'ten çıkar -> round-trip
    svc.apply_scan(_scan(["ETH_USDT"]), T0 + 2 * H + 2)
    assert svc._flap_count.get("BTC_USDT", 0) == 1


def test_one_way_transition_no_flap():
    """Q2=B: tek yönlü giriş flap saymaz."""
    svc = _svc()
    svc.apply_scan(_scan(["BTC_USDT"]), T0)
    svc.apply_scan(_scan(["BTC_USDT"]), T0 + H + 1)
    assert svc._flap_count.get("BTC_USDT", 0) == 0


def test_flap_threshold_triggers_quarantine():
    """Q2/A: threshold asilinca aninda quarantine (level 1)."""
    svc = _svc()
    for i in range(DEFAULT_FLAP_THRESHOLD):
        base = T0 + i * 2 * H
        svc.apply_scan(_scan(["BTC_USDT"]), base)
        svc.apply_scan(_scan(["ETH_USDT"]), base + H + 1)
    assert svc._quarantine_level.get("BTC_USDT") == 1
    assert svc._quarantine_until_ms["BTC_USDT"] > 0


def test_quarantine_blocks_subscribe():
    svc = _svc()
    for i in range(DEFAULT_FLAP_THRESHOLD):
        base = T0 + i * 2 * H
        svc.apply_scan(_scan(["BTC_USDT"]), base)
        svc.apply_scan(_scan(["ETH_USDT"]), base + H + 1)
    # Quarantine aktifken tekrar Top5'e girme denemesi
    t1 = T0 + DEFAULT_FLAP_THRESHOLD * 2 * H + 10
    svc.apply_scan(_scan(["BTC_USDT"]), t1)
    svc.apply_scan(_scan(["BTC_USDT"]), t1 + H + 1)
    assert "BTC_USDT" not in svc.current_subscriptions()


def test_stable_reset_after_7_days():
    """Q3=B: 7 gun karantinasiz stabilite sonrasi level 1."""
    svc = _svc()
    svc._quarantine_level["BTC_USDT"] = 3
    svc._quarantine_until_ms["BTC_USDT"] = T0
    t_after = T0 + DEFAULT_QUARANTINE_RESET_STABLE_MS + 86_400_000
    svc._maybe_stable_reset("BTC_USDT", t_after)
    assert svc._quarantine_level["BTC_USDT"] == 1