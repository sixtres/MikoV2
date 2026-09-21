# src/backtest/data_quality.py
# YAMA Y-353: DI, no global
# B2e.0: minimal gap/completeness detection (SORU Q' temel)

"""
B2e.0 — Data quality detection (minimum).

SORU Q' tam spesifikasyonu (fail-fast + WARNING + strict/lenient
profil) B2e.3'e bırakılmıştır. Bu modül sadece gap tespiti ve
completeness hesabı yapar; eşik/profil politikası uygulamaz.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    symbol: str
    span_sec: int
    sample_count: int
    expected_count: int
    completeness: float
    gap_count: int
    max_gap_sec: int
    gaps: tuple  # tuple[tuple[int, int], ...]

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "span_sec": self.span_sec,
            "sample_count": self.sample_count,
            "expected_count": self.expected_count,
            "completeness": round(self.completeness, 6),
            "gap_count": self.gap_count,
            "max_gap_sec": self.max_gap_sec,
            "gaps": [list(g) for g in self.gaps],
        }


def analyze_ohlcv_secs(
    symbol: str,
    secs: list[int],
    expected_interval_sec: int = 1,
) -> DataQualityReport:
    """
    secs: OHLCV sec degerleri, artan sirada.
    expected_interval_sec: beklenen ornekleme araligi (saniye).
    """
    if not secs:
        return DataQualityReport(
            symbol=symbol, span_sec=0, sample_count=0,
            expected_count=0, completeness=0.0,
            gap_count=0, max_gap_sec=0, gaps=(),
        )
    span = secs[-1] - secs[0]
    expected = (span // expected_interval_sec) + 1 if span >= 0 else 0
    gaps: list[tuple[int, int]] = []
    max_gap = 0
    for i in range(1, len(secs)):
        delta = secs[i] - secs[i - 1]
        if delta > expected_interval_sec:
            gaps.append((secs[i - 1], secs[i]))
            if delta > max_gap:
                max_gap = delta
    completeness = len(secs) / expected if expected > 0 else 0.0
    return DataQualityReport(
        symbol=symbol,
        span_sec=span,
        sample_count=len(secs),
        expected_count=expected,
        completeness=completeness,
        gap_count=len(gaps),
        max_gap_sec=max_gap,
        gaps=tuple(gaps),
    )