"""T6: B3.5-AJ=B pre-day-0 rehearsal.

7 adım; HARD + SOFT katmanlı. Hard herhangi FAIL = NO-GO.
Soft WARN = PO sign-off ile geçebilir. Manuel çalıştırılır.

Kullanım:
    python -m tests.manual.rehearsal_b3_5 --out rehearsal_report.json

Not: Gerçek deploy yapmaz; DI callable'lar ile adımları
yürütür. Callable'lar sağlanmazsa SKIP üretir. Böylece
test ortamında güvenle çalışır ve kanıt toplar.
"""

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional


class Layer(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


class Verdict(str, Enum):
    GO = "GO"
    NO_GO = "NO-GO"
    GO_WITH_PO_SIGNOFF = "GO-WITH-PO-SIGNOFF"


@dataclass
class Step:
    id: str
    name: str
    layer: Layer
    status: Status
    evidence: Dict[str, object] = field(default_factory=dict)
    detail: str = ""


@dataclass
class Report:
    steps: List[Step]
    verdict: Verdict
    hard_failures: List[str]
    soft_warnings: List[str]
    generated_at_ms: int
    durum_evidence: Dict[str, object]


# --- Adım çalıştırıcıları ---

def _run(name: str, layer: Layer, fn: Optional[Callable[[], Step]]) -> Step:
    if fn is None:
        return Step(id=name, name=name, layer=layer,
                    status=Status.SKIP, detail="callable sağlanmadı")
    try:
        return fn()
    except Exception as e:
        return Step(id=name, name=name, layer=layer,
                    status=Status.FAIL, detail=f"exception: {e}")


# HARD #1 — Deploy Z=B snapshot (dry-run doğrulama)
def step_deploy_z_b_snapshot(verify: Optional[Callable[[], bool]]) -> Step:
    if verify is None:
        return Step("H1", "deploy_z_b_snapshot", Layer.HARD,
                    Status.SKIP, detail="verify callable yok")
    ok = bool(verify())
    return Step("H1", "deploy_z_b_snapshot", Layer.HARD,
                Status.PASS if ok else Status.FAIL,
                evidence={"snapshot_verified": ok})


# HARD #2 — pytest full suite
def step_pytest_full(run_pytest: Optional[Callable[[], Dict[str, object]]]) -> Step:
    if run_pytest is None:
        return Step("H2", "pytest_full_suite", Layer.HARD,
                    Status.SKIP, detail="run_pytest callable yok")
    res = run_pytest()
    passed = int(res.get("passed", 0))
    failed = int(res.get("failed", 0))
    errors = int(res.get("errors", 0))
    ok = failed == 0 and errors == 0 and passed > 0
    return Step("H2", "pytest_full_suite", Layer.HARD,
                Status.PASS if ok else Status.FAIL,
                evidence={"passed": passed, "failed": failed,
                          "errors": errors})


# HARD #3 — stop-flag SLA ≤10s
def step_stop_flag_sla(measure_sla_s: Optional[Callable[[], float]]) -> Step:
    if measure_sla_s is None:
        return Step("H3", "stop_flag_sla", Layer.HARD,
                    Status.SKIP, detail="measure callable yok")
    sla = float(measure_sla_s())
    ok = sla <= 10.0
    return Step("H3", "stop_flag_sla", Layer.HARD,
                Status.PASS if ok else Status.FAIL,
                evidence={"sla_s": sla, "threshold_s": 10.0})


# HARD #4 — AH restore integrity_check + row-count
def step_ah_restore(
    restore: Optional[Callable[[], Dict[str, object]]],
) -> Step:
    if restore is None:
        return Step("H4", "ah_restore_integrity", Layer.HARD,
                    Status.SKIP, detail="restore callable yok")
    res = restore()
    integrity = res.get("integrity_check", "unknown")
    row_ok = bool(res.get("row_count_ok", False))
    ok = integrity == "ok" and row_ok
    return Step("H4", "ah_restore_integrity", Layer.HARD,
                Status.PASS if ok else Status.FAIL,
                evidence={"integrity_check": integrity,
                          "row_count_ok": row_ok})


# SOFT #1 — Z=B snapshot bytes doğrulama
def step_z_snapshot_verify(
    verify: Optional[Callable[[], Dict[str, object]]],
) -> Step:
    if verify is None:
        return Step("S1", "z_snapshot_verify", Layer.SOFT,
                    Status.SKIP, detail="verify callable yok")
    res = verify()
    ok = bool(res.get("checksum_ok", False))
    return Step("S1", "z_snapshot_verify", Layer.SOFT,
                Status.PASS if ok else Status.WARN,
                evidence=res)


# SOFT #2 — AG temp instance dry-run
def step_ag_dry_run(
    dry: Optional[Callable[[], Dict[str, object]]],
) -> Step:
    if dry is None:
        return Step("S2", "ag_dry_run", Layer.SOFT,
                    Status.SKIP, detail="dry callable yok")
    res = dry()
    ok = bool(res.get("dry_ok", False))
    fallback = bool(res.get("fallback_used", False))
    if ok:
        return Step("S2", "ag_dry_run", Layer.SOFT,
                    Status.PASS, evidence=res)
    return Step("S2", "ag_dry_run", Layer.SOFT,
                Status.WARN,
                detail=("fallback path kullanıldı (B3.5-AG fallback clause)"
                        if fallback else "dry-run başarısız"),
                evidence=res)


# SOFT #3 — cadence + snapshot bytes ölçümü
def step_cadence_snapshot_bytes(
    measure: Optional[Callable[[], Dict[str, object]]],
) -> Step:
    if measure is None:
        return Step("S3", "cadence_snapshot_bytes", Layer.SOFT,
                    Status.SKIP, detail="measure callable yok")
    res = measure()
    # Q=C %80 disk projeksiyonu aşımı → hard'a terfi
    proj = float(res.get("disk_projection_pct", 0.0))
    if proj >= 80.0:
        return Step("S3", "cadence_snapshot_bytes", Layer.HARD,
                    Status.FAIL,
                    detail=f"Q=C disk projeksiyon %{proj:.1f} >= %80",
                    evidence=res)
    sla_margin = res.get("sla_margin_s")
    if isinstance(sla_margin, (int, float)) and float(sla_margin) <= 0:
        return Step("S3", "cadence_snapshot_bytes", Layer.HARD,
                    Status.FAIL,
                    detail="SLA marjı aşımı — hard'a terfi",
                    evidence=res)
    return Step("S3", "cadence_snapshot_bytes", Layer.SOFT,
                Status.PASS, evidence=res)


def _verdict(steps: List[Step]) -> Verdict:
    hard_fail = any(s.layer == Layer.HARD and s.status == Status.FAIL
                    for s in steps)
    if hard_fail:
        return Verdict.NO_GO
    soft_warn = any(s.layer == Layer.SOFT and s.status == Status.WARN
                    for s in steps)
    soft_fail = any(s.layer == Layer.SOFT and s.status == Status.FAIL
                    for s in steps)
    if soft_warn or soft_fail:
        return Verdict.GO_WITH_PO_SIGNOFF
    return Verdict.GO


def run_rehearsal(
    verify_snapshot: Optional[Callable[[], bool]] = None,
    run_pytest: Optional[Callable[[], Dict[str, object]]] = None,
    measure_sla_s: Optional[Callable[[], float]] = None,
    ah_restore: Optional[Callable[[], Dict[str, object]]] = None,
    z_snapshot_verify: Optional[Callable[[], Dict[str, object]]] = None,
    ag_dry_run: Optional[Callable[[], Dict[str, object]]] = None,
    cadence_measure: Optional[Callable[[], Dict[str, object]]] = None,
) -> Report:
    steps: List[Step] = [
        step_deploy_z_b_snapshot(verify_snapshot),
        step_pytest_full(run_pytest),
        step_stop_flag_sla(measure_sla_s),
        step_ah_restore(ah_restore),
        step_z_snapshot_verify(z_snapshot_verify),
        step_ag_dry_run(ag_dry_run),
        step_cadence_snapshot_bytes(cadence_measure),
    ]
    verdict = _verdict(steps)
    hard_failures = [s.id for s in steps
                     if s.layer == Layer.HARD and s.status == Status.FAIL]
    soft_warnings = [s.id for s in steps
                     if s.layer == Layer.SOFT
                     and s.status in (Status.WARN, Status.FAIL)]
    return Report(
        steps=steps,
        verdict=verdict,
        hard_failures=hard_failures,
        soft_warnings=soft_warnings,
        generated_at_ms=int(time.time() * 1000),
        durum_evidence={
            "verdict": verdict.value,
            "hard_failures": hard_failures,
            "soft_warnings": soft_warnings,
            "step_count": len(steps),
        },
    )


def render_markdown(report: Report) -> str:
    lines: List[str] = []
    lines.append("# B3.5 Rehearsal Raporu")
    lines.append("")
    lines.append(f"- Verdict: **{report.verdict.value}**")
    lines.append(f"- generated_at_ms: {report.generated_at_ms}")
    lines.append("")
    lines.append("| ID | Adım | Katman | Durum | Detay |")
    lines.append("|---|---|---|---|---|")
    for s in report.steps:
        lines.append(f"| {s.id} | {s.name} | {s.layer.value} "
                     f"| {s.status.value} | {s.detail or '-'} |")
    lines.append("")
    if report.hard_failures:
        lines.append(f"**HARD FAILURES**: {report.hard_failures}")
    if report.soft_warnings:
        lines.append(f"**SOFT WARNINGS**: {report.soft_warnings} "
                     "(PO sign-off gerekli)")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="rehearsal_report.json")
    p.add_argument("--md", default="rehearsal_report.md")
    args = p.parse_args(argv)

    # Manuel modda callable'lar PO tarafından sağlanır.
    # Bu CLI gerçek çalıştırmada SKIP üretir ve iskeleti verir.
    report = run_rehearsal()
    Path(args.out).write_text(
        json.dumps(
            {
                "verdict": report.verdict.value,
                "hard_failures": report.hard_failures,
                "soft_warnings": report.soft_warnings,
                "steps": [asdict(s) for s in report.steps],
                "generated_at_ms": report.generated_at_ms,
                "durum_evidence": report.durum_evidence,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    Path(args.md).write_text(render_markdown(report), encoding="utf-8")
    print(f"verdict={report.verdict.value} out={args.out} md={args.md}")
    return 0 if report.verdict != Verdict.NO_GO else 1


if __name__ == "__main__":
    raise SystemExit(main())