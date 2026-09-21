# tests/unit/test_backtest_multi_report.py
# B2e.3 — multi_report.build_report testleri.
# Kararlar: UU=A, VV=A, WW=C, XX=B, YY=A, ZZ=A, AA'=A, BB'=C.

from __future__ import annotations

import pytest

from src.backtest.multi_report import (
    CLAIM_CAPABLE,
    CLAIM_MULTI_SYMBOL_REAL,
    CLAIM_SINGLE_SYMBOL_REAL,
    CLAIM_SYNTHETIC_VALIDATED,
    PROFILE_LEGACY,
    PROFILE_LENIENT,
    PROFILE_STRICT,
    SCHEMA_VERSION,
    _coverage_report,
    _dropped_aggregation,
    build_report,
)


# ============================================================ sabitler


def test_schema_version_is_one() -> None:
    assert SCHEMA_VERSION == 1


def test_profile_choices_distinct() -> None:
    assert {PROFILE_LEGACY, PROFILE_LENIENT, PROFILE_STRICT} == {
        "legacy", "lenient", "strict",
    }


def test_claim_constants_distinct() -> None:
    assert len({
        CLAIM_CAPABLE, CLAIM_SYNTHETIC_VALIDATED,
        CLAIM_SINGLE_SYMBOL_REAL, CLAIM_MULTI_SYMBOL_REAL,
    }) == 4


# ============================================================ build_report temel


def test_build_report_single_minimal() -> None:
    payloads = {"mode": "single", "result": {}}
    rep = build_report(
        payloads,
        symbols=["BTC_USDT"],
        ohlcv_secs_by_symbol={"BTC_USDT": list(range(100))},
    )
    assert rep["schema_version"] == SCHEMA_VERSION
    assert rep["mode"] == "single"
    assert rep["profile"] == PROFILE_LEGACY
    assert rep["multi_symbol_capable"] is False
    # SORU T: "single_symbol_real_walkforward_executed" walk-forward
    # gerektirir; mode=single walk-forward değil → False.
    assert rep["single_symbol_real_walkforward_executed"] is False
    assert rep["real_multi_symbol_validated"] is False
    assert rep["walk_forward_claim"] == CLAIM_CAPABLE
    assert rep["real_data_symbols"] == ["BTC_USDT"]
    assert rep["fold_count"] == 0
    assert rep["single_fold_warning"] is False
    assert rep["fold_windows"] == []
    assert "data_quality" in rep
    assert "ticker_coverage" in rep
    assert "depth_coverage" in rep
    assert "excluded_symbols" in rep


def test_build_report_source_passthrough() -> None:
    inner = {"trades": [{"symbol": "BTC_USDT"}]}
    payloads = {"mode": "single", "result": inner}
    rep = build_report(payloads, symbols=["BTC_USDT"])
    assert rep["source"] is payloads
    assert rep["source"]["result"] is inner


def test_build_report_multi_mode_flags() -> None:
    payloads = {
        "mode": "multi",
        "result": {
            "trades": [
                {"symbol": "BTC_USDT"},
                {"symbol": "ETH_USDT"},
            ],
            "dropped_entries": [],
        },
    }
    rep = build_report(payloads)
    assert rep["mode"] == "multi"
    assert rep["multi_symbol_capable"] is True
    assert rep["real_data_symbols"] == ["BTC_USDT", "ETH_USDT"]
    assert rep["single_symbol_real_walkforward_executed"] is False
    assert rep["real_multi_symbol_validated"] is False


def test_build_report_walkforward_folds() -> None:
    payloads = {
        "mode": "walkforward",
        "result": {
            "fold_count": 2,
            "single_fold_warning": False,
            "folds": [
                {
                    "window": {"fold_id": 0, "train_start_ms": 0},
                    "trades": [{"symbol": "BTC_USDT"}],
                },
                {
                    "window": {"fold_id": 1, "train_start_ms": 100},
                    "trades": [{"symbol": "BTC_USDT"}],
                },
            ],
            "combined_trades": [{"symbol": "BTC_USDT"}],
            "combined_dropped": [],
        },
    }
    rep = build_report(payloads)
    assert rep["mode"] == "walkforward"
    assert rep["fold_count"] == 2
    assert rep["single_fold_warning"] is False
    assert len(rep["fold_windows"]) == 2
    assert rep["fold_windows"][0]["fold_id"] == 0
    assert rep["real_data_symbols"] == ["BTC_USDT"]


# ============================================================ dropped A3


def test_dropped_aggregation_reason_and_symbol() -> None:
    dropped = [
        {"reason": "global_limit_full", "symbol": "BTC_USDT", "ts_ms": 1},
        {"reason": "global_limit_full", "symbol": "BTC_USDT", "ts_ms": 2},
        {"reason": "cooldown_active", "symbol": "ETH_USDT", "ts_ms": 3},
    ]
    by_reason, by_symbol = _dropped_aggregation(dropped)
    assert by_reason == {
        "global_limit_full": 2, "cooldown_active": 1,
    }
    assert by_symbol == {"BTC_USDT": 2, "ETH_USDT": 1}


def test_build_report_global_limit_exercised() -> None:
    payloads = {
        "mode": "multi",
        "result": {
            "trades": [],
            "dropped_entries": [
                {"reason": "global_limit_full", "symbol": "X", "ts_ms": 1},
            ],
        },
    }
    rep = build_report(payloads)
    assert rep["global_limit_exercised"] is True
    assert rep["dropped_entries_count"] == 1
    assert rep["dropped_entries_by_reason"] == {"global_limit_full": 1}


# ============================================================ coverage XX


def test_coverage_distinct_secs_dedup() -> None:
    # 4 raw sec, 3 distinct → distinct üzerinden hesaplanır.
    cov = _coverage_report({"X": [1, 1, 1, 2, 3]}, 1)
    sym = cov["by_symbol"]["X"]
    assert sym["sample_count"] == 3  # 1, 2, 3
    assert sym["completeness"] == 1.0
    assert cov["collector_rate_anomaly"] is True


def test_coverage_no_anomaly_when_no_duplicates() -> None:
    cov = _coverage_report({"X": [1, 2, 3, 4, 5]}, 1)
    assert cov["collector_rate_anomaly"] is False


def test_coverage_empty_secs() -> None:
    cov = _coverage_report({"X": []}, 60)
    assert cov["by_symbol"]["X"]["completeness"] == 0.0
    assert cov["aggregate"]["min_completeness"] == 0.0
    assert cov["aggregate"]["max_gap_ms"] == 0


# ============================================================ profil YY


def test_profile_legacy_never_fails() -> None:
    payloads = {"mode": "single", "result": {}}
    # completeness ~0.5 → legacy tolerates
    secs = [i * 2 for i in range(50)]
    rep = build_report(
        payloads, profile=PROFILE_LEGACY,
        ohlcv_secs_by_symbol={"BTC_USDT": secs},
    )
    dq = rep["data_quality"]
    assert dq["profile"] == PROFILE_LEGACY
    assert dq["warnings"] == []
    assert dq["fail_fast_triggered"] is False


def test_profile_lenient_warning_but_no_fail() -> None:
    payloads = {"mode": "single", "result": {}}
    secs = [i * 2 for i in range(50)]  # ~0.5 completeness
    rep = build_report(
        payloads, profile=PROFILE_LENIENT,
        ohlcv_secs_by_symbol={"BTC_USDT": secs},
    )
    dq = rep["data_quality"]
    assert dq["profile"] == PROFILE_LENIENT
    assert len(dq["warnings"]) >= 1
    assert dq["fail_fast_triggered"] is False


def test_profile_strict_fail_fast_raises() -> None:
    payloads = {"mode": "single", "result": {}}
    secs = [i * 2 for i in range(50)]  # ~0.5 completeness < 0.95
    with pytest.raises(RuntimeError, match="strict"):
        build_report(
            payloads, profile=PROFILE_STRICT,
            ohlcv_secs_by_symbol={"BTC_USDT": secs},
        )


def test_profile_unknown_raises() -> None:
    payloads = {"mode": "single", "result": {}}
    with pytest.raises(ValueError, match="unknown profile"):
        build_report(payloads, profile="bogus")


# ============================================================ excluded BB'


def test_excluded_all_and_effective() -> None:
    all_excluded = frozenset({"XAUT_USDT", "SILVER_USDT", "GOLD_USDT"})
    payloads = {"mode": "single", "result": {}}
    rep = build_report(
        payloads,
        excluded_symbols_all=all_excluded,
        excluded_symbols_version=1,
        requested_symbols=["BTC_USDT", "XAUT_USDT"],
    )
    ex = rep["excluded_symbols"]
    assert ex["all"] == ["GOLD_USDT", "SILVER_USDT", "XAUT_USDT"]
    assert ex["effective"] == ["XAUT_USDT"]
    assert ex["version"] == 1


def test_excluded_effective_empty_when_no_requested_match() -> None:
    payloads = {"mode": "single", "result": {}}
    rep = build_report(
        payloads,
        excluded_symbols_all=frozenset({"XAUT_USDT"}),
        excluded_symbols_version=1,
        requested_symbols=["BTC_USDT", "ETH_USDT"],
    )
    assert rep["excluded_symbols"]["effective"] == []
    assert rep["excluded_symbols"]["all"] == ["XAUT_USDT"]


# ============================================================ claim ZZ


def test_claim_derived_from_flags_capable_only() -> None:
    payloads = {"mode": "multi", "result": {"trades": [], "dropped_entries": []}}
    rep = build_report(payloads)
    # multi_symbol_capable=True, synthetic=False, real=False
    assert rep["walk_forward_claim"] == CLAIM_CAPABLE


def test_claim_synthetic_validated_beats_capable() -> None:
    payloads = {"mode": "multi", "result": {"trades": [], "dropped_entries": []}}
    rep = build_report(payloads, synthetic_validated=True)
    assert rep["walk_forward_claim"] == CLAIM_SYNTHETIC_VALIDATED


def test_claim_multi_symbol_real_when_4_symbols_walkforward() -> None:
    symbols = ["A_USDT", "B_USDT", "C_USDT", "D_USDT"]
    payloads = {
        "mode": "walkforward",
        "result": {
            "fold_count": 1,
            "single_fold_warning": True,
            "folds": [],
            "combined_trades": [{"symbol": s} for s in symbols],
            "combined_dropped": [],
        },
    }
    rep = build_report(payloads)
    assert rep["real_multi_symbol_validated"] is True
    assert rep["walk_forward_claim"] == CLAIM_MULTI_SYMBOL_REAL


def test_claim_not_single_symbol_real_for_single_mode() -> None:
    """
    mode=single, 1 sembol → walk-forward koşmadı; claim capable
    seviyesinde kalır (SORU T'nin 'walkforward' kelimesi).
    """
    payloads = {"mode": "single", "result": {}}
    rep = build_report(payloads, symbols=["BTC_USDT"])
    assert rep["single_symbol_real_walkforward_executed"] is False
    assert rep["walk_forward_claim"] == CLAIM_CAPABLE


def test_claim_single_symbol_real_for_walkforward_one_symbol() -> None:
    """SORU T: walkforward + 1 sembol → single_symbol_real."""
    payloads = {
        "mode": "walkforward",
        "result": {
            "fold_count": 2,
            "single_fold_warning": False,
            "folds": [],
            "combined_trades": [{"symbol": "BTC_USDT"}],
            "combined_dropped": [],
        },
    }
    rep = build_report(payloads)
    assert rep["single_symbol_real_walkforward_executed"] is True
    assert rep["multi_symbol_capable"] is True
    assert rep["real_multi_symbol_validated"] is False
    assert rep["walk_forward_claim"] == CLAIM_SINGLE_SYMBOL_REAL


# ============================================================ gaps budama WW


def test_gaps_sample_truncated_when_many_gaps() -> None:
    # 200 secs, her 2 adım → 199 saniye aralık, çok gap
    secs = [i * 2 for i in range(200)]
    cov = _coverage_report({"X": secs}, 1)
    sym = cov["by_symbol"]["X"]
    assert sym["gap_count"] == 199
    assert len(sym["gaps_sample"]) == 10  # _GAPS_SAMPLE_MAX
    assert sym["gaps_truncated"] is True


def test_gaps_sample_not_truncated_when_few_gaps() -> None:
    secs = [1, 2, 4, 5]  # 1 gap: (2,4)
    cov = _coverage_report({"X": secs}, 1)
    sym = cov["by_symbol"]["X"]
    assert sym["gap_count"] == 1
    assert sym["gaps_truncated"] is False
    assert len(sym["gaps_sample"]) == 1