# YAMA Y-267, Y-268, Y-353, Y-358
# REV7: Universe scanner tests

import pytest

from src.data_layer.universe_scanner import (
    ScannerConfig,
    SymbolMetrics,
    UniverseScanner,
    UniverseStatus,
)


def _make_scanner(**overrides):
    cfg = ScannerConfig(**overrides)
    return UniverseScanner(cfg)


def _mk_metrics(symbol, oi_usd=100_000_000.0, spread_bps=10.0, **kwargs):
    return SymbolMetrics(
        symbol=symbol, oi_usd=oi_usd, spread_bps=spread_bps, **kwargs
    )


def test_config_defaults():
    cfg = ScannerConfig()
    assert cfg.max_top == 5
    assert cfg.max_watch == 10
    assert cfg.min_oi_usd == 50_000_000.0
    assert cfg.hysteresis_ms == 300_000
    assert cfg.max_pending_ms == 600_000
    assert cfg.flap_threshold == 3
    assert cfg.always_include == ("BTC_USDT",)


def test_no_global_state():
    assert not hasattr(UniverseScanner, "_states")


def test_refresh_empty_returns_only_always_include():
    s = _make_scanner()
    result = s.refresh([])
    # BTC_USDT always_include, hiçbir metrics olmasa bile IN_TOP5
    assert result == {"BTC_USDT": UniverseStatus.IN_TOP5}


def test_always_include_btcusdt():
    s = _make_scanner(always_include=("BTC_USDT",))
    result = s.refresh([])
    # BTC_USDT is always included even with no metrics
    assert result.get("BTC_USDT") == UniverseStatus.IN_TOP5


def test_top5_selection():
    s = _make_scanner()
    metrics = [
        _mk_metrics("BTC_USDT", oi_change=0.1),
        _mk_metrics("ETH_USDT", oi_change=0.9),  # higher score
        _mk_metrics("SOL_USDT", oi_change=0.5),
        _mk_metrics("XRP_USDT", oi_change=0.3),
        _mk_metrics("DOGE_USDT", oi_change=0.8),
        _mk_metrics("AVAX_USDT", oi_change=0.7),  # 6th
    ]
    result = s.refresh(metrics)
    top5 = s.get_top5()
    assert len(top5) == 5
    # ETH, DOGE, AVAX, SOL, XRP? BTC always included
    assert "BTC_USDT" in top5
    assert "ETH_USDT" in top5


def test_gate_filters_low_oi():
    s = _make_scanner()
    metrics = [
        _mk_metrics("LOW_OI", oi_usd=10_000_000.0, oi_change=1.0),
        _mk_metrics("BTC_USDT"),
    ]
    s.refresh(metrics)
    # LOW_OI doesn't pass gate
    assert s.get_status("LOW_OI") == UniverseStatus.DROPPED


def test_gate_filters_low_spread():
    s = _make_scanner()
    metrics = [
        _mk_metrics("TIGHT", spread_bps=2.0),
        _mk_metrics("BTC_USDT"),
    ]
    s.refresh(metrics)
    assert s.get_status("TIGHT") == UniverseStatus.DROPPED


def test_gate_filters_high_spread():
    s = _make_scanner()
    metrics = [
        _mk_metrics("WIDE", spread_bps=50.0),
        _mk_metrics("BTC_USDT"),
    ]
    s.refresh(metrics)
    assert s.get_status("WIDE") == UniverseStatus.DROPPED


def test_hysteresis_keeps_in_top5_briefly():
    """A symbol dropping out of top5 for <5m stays IN_TOP5."""
    s = _make_scanner(always_include=("BTC_USDT",))
    # Round 1: A is in top5
    m1 = [
        _mk_metrics("BTC_USDT"),
        _mk_metrics("A", oi_change=1.0),
    ]
    s.refresh(m1)
    assert s.get_status("A") == UniverseStatus.IN_TOP5

    # Round 2: A drops out (new symbol B joins with higher score)
    m2 = [
        _mk_metrics("BTC_USDT"),
        _mk_metrics("B", oi_change=2.0),
        _mk_metrics("A", oi_change=0.0),
        _mk_metrics("C", oi_change=1.5),
        _mk_metrics("D", oi_change=1.4),
        _mk_metrics("E", oi_change=1.3),
    ]
    s.refresh(m2)
    # A should still be IN_TOP5 due to hysteresis
    assert s.get_status("A") == UniverseStatus.IN_TOP5


def test_max_pending_transitions_to_dropped():
    """OUTSIDE_PENDING -> DROPPED with max_pending=0."""
    s = _make_scanner(
        always_include=("BTC_USDT",),
        hysteresis_ms=0,
        max_pending_ms=0,
        flap_threshold=999,
    )
    m1 = [_mk_metrics("BTC_USDT"), _mk_metrics("A", oi_change=1.0)]
    s.refresh(m1)
    assert s.get_status("A") == UniverseStatus.IN_TOP5

    # Round 2: A drops out (12 rakip, top10'u doldur)
    m2 = [_mk_metrics("BTC_USDT"), _mk_metrics("A", oi_change=-10.0)]
    for i, name in enumerate(["B","C","D","E","F","G","H","I","J","K","L"]):
        m2.append(_mk_metrics(name, oi_change=2.0 - i * 0.1))
    s.refresh(m2)  # IN_TOP5 -> OUTSIDE_PENDING
    assert s.get_status("A") == UniverseStatus.OUTSIDE_PENDING

    # Round 3: OUTSIDE_PENDING -> DROPPED
    s.refresh(m2)
    assert s.get_status("A") == UniverseStatus.DROPPED


def test_get_active_symbols():
    s = _make_scanner()
    metrics = [
        _mk_metrics("BTC_USDT", oi_change=0.5),
        _mk_metrics("ETH_USDT", oi_change=0.4),
    ]
    s.refresh(metrics)
    active = s.get_active_symbols()
    assert "BTC_USDT" in active
    assert "ETH_USDT" in active


def test_status_counts():
    s = _make_scanner()
    metrics = [_mk_metrics("BTC_USDT")]
    s.refresh(metrics)
    counts = s.status_counts()
    assert counts.get("IN_TOP5", 0) >= 1


def test_unknown_symbol_status():
    s = _make_scanner()
    assert s.get_status("NONEXIST") == UniverseStatus.UNKNOWN


def test_flap_protection_keeps_status_stable():
    """With flap_threshold=3 and rapid changes, status stays IN_TOP5."""
    s = _make_scanner(
        always_include=("BTC_USDT",),
        hysteresis_ms=0,
        flap_threshold=3,
        flap_window_ms=300_000,
    )
    # Round 1: A in top5
    s.refresh([_mk_metrics("BTC_USDT"), _mk_metrics("A", oi_change=1.0)])
    assert s.get_status("A") == UniverseStatus.IN_TOP5

    # Round 2-4: A drops out 3 times -> flap_count reaches 3
    for _ in range(3):
        s.refresh([
            _mk_metrics("BTC_USDT"),
            _mk_metrics("B", oi_change=2.0),
            _mk_metrics("C", oi_change=1.9),
            _mk_metrics("D", oi_change=1.8),
            _mk_metrics("E", oi_change=1.7),
            _mk_metrics("A", oi_change=-5.0),
        ])
    # After 3 flaps within window, A should be protected (still in top5)
    # or at least not DROPPED
    status = s.get_status("A")
    assert status in (UniverseStatus.IN_TOP5, UniverseStatus.IN_TOP10)


def test_scoring_weights_sum():
    """Weights should sum to 1.0 for consistency."""
    cfg = ScannerConfig()
    total = (
        cfg.weight_oi_change
        + cfg.weight_liq
        + cfg.weight_squeeze
        + cfg.weight_funding
        + cfg.weight_spread
    )
    assert abs(total - 1.0) < 1e-9