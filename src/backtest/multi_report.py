# src/backtest/multi_report.py
# YAMA Y-353: DI, no global
# B2e.3 — Genişletilmiş rapor (DURUM §8 + §16)
#
# Kilitli kararlar:
#   SORU UU (A): build_report(payloads, *, schema_version, profile) → dict
#   SORU VV (A): SCHEMA_VERSION = 1 (modül sabiti; additive değişiklikte artır)
#   SORU WW (C): data_quality{profile, by_symbol, aggregate}
#   SORU XX (B): coverage = analyze_ohlcv_secs(secs, expected_interval_sec)
#                caller sorted(set(secs)) verir (duplicate → anomaly flag)
#   SORU YY (A): strict profil fail-fast → RuntimeError
#   SORU ZZ (A): walk_forward_claim enum (bayraklardan türetilir)
#   SORU AA′ (A): profile legacy | lenient | strict (default legacy)
#   SORU BB′ (C): excluded_symbols{all, effective, version}
#   SORU T: single_symbol_real_walkforward_executed yalnızca
#           mode=walkforward + 1 sembol ile True (kapanış kriteri).
#
# Risk notları (dış ajan konsensüsü):
#   - Payload tip güvenliği: caller sözleşmesi dar (dict[str, dict]).
#   - by_symbol.gaps top-N ile budanır (BTC_USDT 423 gap).
#   - Duplicate secs → collector_rate_anomaly=True (log + rapor).
#   - walk_forward_claim T'nin kümülatif seviyelerinden türetilir.

from __future__ import annotations

import logging
from typing import Any, Iterable

from .data_quality import analyze_ohlcv_secs

logger = logging.getLogger(__name__)

# SORU VV (A)
SCHEMA_VERSION = 1

# SORU ZZ (A) — T'nin kümülatif seviyeleri
CLAIM_CAPABLE = "capable"
CLAIM_SYNTHETIC_VALIDATED = "synthetic_validated"
CLAIM_SINGLE_SYMBOL_REAL = "single_symbol_real"
CLAIM_MULTI_SYMBOL_REAL = "multi_symbol_real"

# SORU AA′ (A) — profiller
PROFILE_LEGACY = "legacy"
PROFILE_LENIENT = "lenient"
PROFILE_STRICT = "strict"
_PROFILE_CHOICES = (PROFILE_LEGACY, PROFILE_LENIENT, PROFILE_STRICT)

# SORU A2 + OO (B) — eşikler
_STRICT_MIN_COMPLETENESS = 0.95
_STRICT_MAX_GAP_MS = 30 * 60 * 1000
_LENIENT_MIN_COMPLETENESS = 0.85
_LENIENT_MAX_GAP_MS = 60 * 60 * 1000

# Kolektör aralıkları (saniye)
_OHLCV_INTERVAL_SEC = 1
_TICKER_INTERVAL_SEC = 60
_DEPTH_INTERVAL_SEC = 60

# WW risk notu — gaps budama
_GAPS_SAMPLE_MAX = 10


# --------------------------------------------------------------------- profile


def _apply_profile(
    profile: str, aggregate: dict[str, Any]
) -> tuple[bool, list[str]]:
    """
    SORU A2 + YY: eşik kontrolü.
    Dönüş: (fail_fast_triggered, warnings).
    legacy → (False, []); lenient → (False, [warn...]);
    strict → eşik aşımı (True, [warn]) / aksi (False, []).
    """
    if profile == PROFILE_LEGACY:
        return False, []
    if profile == PROFILE_LENIENT:
        warnings: list[str] = []
        c = aggregate.get("min_completeness", 1.0)
        g = aggregate.get("max_gap_ms", 0)
        if c < _LENIENT_MIN_COMPLETENESS:
            warnings.append(
                f"lenient_completeness_below:{c:.4f}"
            )
        if g > _LENIENT_MAX_GAP_MS:
            warnings.append(f"lenient_max_gap_exceeded:{g}")
        return False, warnings
    if profile == PROFILE_STRICT:
        c = aggregate.get("min_completeness", 1.0)
        g = aggregate.get("max_gap_ms", 0)
        violated = (
            c < _STRICT_MIN_COMPLETENESS
            or g > _STRICT_MAX_GAP_MS
        )
        if violated:
            return True, [
                f"strict_violated:completeness={c:.4f},max_gap_ms={g}"
            ]
        return False, []
    raise ValueError(
        f"unknown profile: {profile!r}; expected one of {_PROFILE_CHOICES}"
    )


# --------------------------------------------------------------------- coverage


def _coverage_report(
    secs_by_symbol: dict[str, list[int]],
    expected_interval_sec: int,
) -> dict[str, Any]:
    """
    SORU XX (B): analyze_ohlcv_secs(secs, expected_interval_sec).
    Duplicate secs → distinct'e indirger; collector_rate_anomaly=True.
    """
    by_symbol: dict[str, dict[str, Any]] = {}
    min_completeness = 1.0
    max_gap_ms = 0
    anomaly = False

    for sym, secs in secs_by_symbol.items():
        if not secs:
            by_symbol[sym] = {
                "completeness": 0.0,
                "sample_count": 0,
                "expected_count": 0,
                "span_sec": 0,
                "max_gap_sec": 0,
                "gap_count": 0,
                "gaps_sample": [],
                "gaps_truncated": False,
            }
            min_completeness = 0.0
            continue

        distinct = sorted(set(secs))
        if len(distinct) != len(secs):
            anomaly = True
            logger.warning(
                "coverage: duplicate secs for %s (%d raw, %d distinct); "
                "using distinct",
                sym, len(secs), len(distinct),
            )

        rep = analyze_ohlcv_secs(sym, distinct, expected_interval_sec)
        gaps_list = [list(g) for g in rep.gaps]
        by_symbol[sym] = {
            "completeness": round(rep.completeness, 6),
            "sample_count": rep.sample_count,
            "expected_count": rep.expected_count,
            "span_sec": rep.span_sec,
            "max_gap_sec": rep.max_gap_sec,
            "gap_count": rep.gap_count,
            "gaps_sample": gaps_list[:_GAPS_SAMPLE_MAX],
            "gaps_truncated": rep.gap_count > _GAPS_SAMPLE_MAX,
        }
        if rep.completeness < min_completeness:
            min_completeness = rep.completeness
        gap_ms = rep.max_gap_sec * 1000
        if gap_ms > max_gap_ms:
            max_gap_ms = gap_ms

    return {
        "by_symbol": by_symbol,
        "aggregate": {
            "min_completeness": round(min_completeness, 6),
            "max_gap_ms": max_gap_ms,
            "symbol_count": len(by_symbol),
        },
        "collector_rate_anomaly": anomaly,
    }


def _data_quality_report(
    coverage: dict[str, Any],
    profile: str,
    warnings: list[str],
    fail_fast: bool,
) -> dict[str, Any]:
    """
    SORU WW (C): by_symbol + aggregate.
    G′ literal alan adları (profile, completeness, max_gap_ms, gaps)
    aggregate seviyesinde korunur; profile aggregate'te bir kez yaşar.
    """
    aggregate = dict(coverage["aggregate"])
    aggregate["profile"] = profile
    return {
        "profile": profile,
        "by_symbol": coverage["by_symbol"],
        "aggregate": aggregate,
        "warnings": warnings,
        "fail_fast_triggered": fail_fast,
    }


# --------------------------------------------------------------------- dropped


def _dropped_aggregation(
    dropped: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, int]]:
    """SORU A3 (B): reason × symbol sayımı (raw liste bozulmaz)."""
    by_reason: dict[str, int] = {}
    by_symbol: dict[str, int] = {}
    for d in dropped:
        r = str(d.get("reason", "unknown"))
        s = str(d.get("symbol", "unknown"))
        by_reason[r] = by_reason.get(r, 0) + 1
        by_symbol[s] = by_symbol.get(s, 0) + 1
    return by_reason, by_symbol


# --------------------------------------------------------------------- claim


def _compute_claim(
    *,
    multi_symbol_capable: bool,
    synthetic_validated: bool,
    single_symbol_real: bool,
    multi_symbol_real: bool,
) -> str:
    """
    SORU ZZ (A): en yüksek başarılan seviye. Dört G′ boolean
    bayrağından türetilir; elle yazılmaz.
    """
    if multi_symbol_real:
        return CLAIM_MULTI_SYMBOL_REAL
    if single_symbol_real:
        return CLAIM_SINGLE_SYMBOL_REAL
    if synthetic_validated:
        return CLAIM_SYNTHETIC_VALIDATED
    if multi_symbol_capable:
        return CLAIM_CAPABLE
    return CLAIM_CAPABLE


# --------------------------------------------------------------------- excluded


def _excluded_report(
    all_excluded: frozenset | None,
    version: int,
    requested: Iterable[str] | None,
) -> dict[str, Any]:
    """SORU BB′ (C): all + effective + version."""
    all_set = set(all_excluded) if all_excluded else set()
    req = set(requested) if requested else set()
    effective = sorted(req.intersection(all_set))
    return {
        "all": sorted(all_set),
        "effective": effective,
        "version": int(version),
    }


# --------------------------------------------------------------------- build


def build_report(
    payloads: dict[str, Any],
    *,
    schema_version: int = SCHEMA_VERSION,
    profile: str = PROFILE_LEGACY,
    symbols: list[str] | None = None,
    synthetic_validated: bool = False,
    excluded_symbols_all: frozenset | None = None,
    excluded_symbols_version: int = 0,
    requested_symbols: Iterable[str] | None = None,
    ohlcv_secs_by_symbol: dict[str, list[int]] | None = None,
    ticker_secs_by_symbol: dict[str, list[int]] | None = None,
    depth_secs_by_symbol: dict[str, list[int]] | None = None,
) -> dict[str, Any]:
    """
    SORU UU (A): saf fonksiyon.

    payloads:
      {"mode": "single"|"multi"|"walkforward", "result": {...}}

    Strict profil eşik aşımı → RuntimeError (SORU YY=A).
    """
    if profile not in _PROFILE_CHOICES:
        raise ValueError(
            f"unknown profile: {profile!r}; "
            f"expected one of {_PROFILE_CHOICES}"
        )
    if not isinstance(payloads, dict):
        raise TypeError("payloads must be a dict")

    mode = str(payloads.get("mode", "single"))
    if mode not in ("single", "multi", "walkforward"):
        raise ValueError(f"unknown mode: {mode!r}")

    result = payloads.get("result", {})
    if not isinstance(result, dict):
        raise TypeError("payloads['result'] must be a dict")

    folds = result.get("folds", []) if mode == "walkforward" else []

    # --- coverage (XX)
    dq_ohlcv = _coverage_report(
        ohlcv_secs_by_symbol or {}, _OHLCV_INTERVAL_SEC
    )
    ticker_cov = _coverage_report(
        ticker_secs_by_symbol or {}, _TICKER_INTERVAL_SEC
    )
    depth_cov = _coverage_report(
        depth_secs_by_symbol or {}, _DEPTH_INTERVAL_SEC
    )

    # --- profil (YY)
    fail_fast, warnings = _apply_profile(profile, dq_ohlcv["aggregate"])
    if fail_fast:
        raise RuntimeError(
            f"data_quality strict profile violated: {warnings}"
        )
    data_quality = _data_quality_report(
        dq_ohlcv, profile, warnings, fail_fast,
    )

    # --- dropped (A3)
    if mode == "walkforward":
        dropped = list(result.get("combined_dropped", []))
    else:
        dropped = list(result.get("dropped_entries", []))
    by_reason, by_symbol_drop = _dropped_aggregation(dropped)

    # --- symbols
    real_data_symbols: list[str] = []
    if symbols:
        real_data_symbols = sorted(set(symbols))
    else:
        for t in result.get("trades", []):
            s = t.get("symbol")
            if s:
                real_data_symbols.append(s)
        for t in result.get("combined_trades", []):
            s = t.get("symbol")
            if s:
                real_data_symbols.append(s)
        for f in folds:
            for t in f.get("trades", []):
                s = t.get("symbol")
                if s:
                    real_data_symbols.append(s)
        real_data_symbols = sorted(set(real_data_symbols))

    # --- bayraklar
    multi_symbol_capable = mode in ("multi", "walkforward")
    # SORU T: "single-symbol real walk-forward" kapanış kriteri.
    # Alan adı walkforward içerdiği için yalnızca walkforward
    # modunda 1 sembolle işaretlenir.
    single_symbol_real = (
        mode == "walkforward" and len(real_data_symbols) == 1
    )
    multi_symbol_real = (
        mode == "walkforward" and len(real_data_symbols) >= 4
    )
    claim = _compute_claim(
        multi_symbol_capable=multi_symbol_capable,
        synthetic_validated=bool(synthetic_validated),
        single_symbol_real=single_symbol_real,
        multi_symbol_real=multi_symbol_real,
    )

    # --- fold_windows / counts
    fold_windows = [
        f.get("window") for f in folds
    ] if mode == "walkforward" else []
    fold_count = (
        int(result.get("fold_count", 0)) if mode == "walkforward" else 0
    )
    single_fold_warning = bool(
        result.get("single_fold_warning", False)
        if mode == "walkforward" else False
    )

    # --- excluded (BB′)
    excluded = _excluded_report(
        excluded_symbols_all, excluded_symbols_version, requested_symbols,
    )

    return {
        "schema_version": int(schema_version),
        "mode": mode,
        "profile": profile,
        "multi_symbol_capable": multi_symbol_capable,
        "synthetic_multi_symbol_validated": bool(synthetic_validated),
        "real_multi_symbol_validated": multi_symbol_real,
        "single_symbol_real_walkforward_executed": single_symbol_real,
        "real_data_symbols": real_data_symbols,
        "data_quality": data_quality,
        "ticker_coverage": ticker_cov,
        "depth_coverage": depth_cov,
        "global_limit_exercised": by_reason.get("global_limit_full", 0) > 0,
        "dropped_entries_count": len(dropped),
        "dropped_entries": dropped,
        "dropped_entries_by_reason": by_reason,
        "dropped_entries_by_symbol": by_symbol_drop,
        "excluded_symbols": excluded,
        "fold_count": fold_count,
        "single_fold_warning": single_fold_warning,
        "walk_forward_claim": claim,
        "fold_windows": fold_windows,
        "source": payloads,
    }