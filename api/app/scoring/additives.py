"""Additive penalty, the A component (specs/003-additives.md)."""

from dataclasses import dataclass

from app.scoring.config import AdditivesConfig
from app.scoring.types import AdditiveInfo, BreakdownLine

RISK_WORDS = {
    0: "no estimated overexposure risk",
    1: "low estimated overexposure risk",
    2: "moderate estimated overexposure risk",
    3: "high estimated overexposure risk",
}


@dataclass(frozen=True)
class AdditivesResult:
    known: bool
    value: float | None
    cap_applies: bool
    lines: tuple[BreakdownLine, ...]


def unique_sorted(additives: tuple[AdditiveInfo, ...]) -> list[AdditiveInfo]:
    """One entry per code, in code order, so output never depends on input order (ADD-4)."""
    by_code: dict[str, AdditiveInfo] = {}
    for a in additives:
        by_code.setdefault(a.code, a)
    return [by_code[c] for c in sorted(by_code)]


def compute(additives: tuple[AdditiveInfo, ...] | None, cfg: AdditivesConfig) -> AdditivesResult:
    if additives is None:  # ADD-6
        return AdditivesResult(False, None, False, ())

    total_penalty = 0.0
    cap_applies = False
    lines: list[BreakdownLine] = []
    for a in unique_sorted(additives):
        source = a.source_url or cfg.off_facet_url.format(code=a.code)
        info = {"name": a.name, "risk_level": a.risk_level, "evidence_grade": a.evidence_grade}
        if a.risk_level is None or a.evidence_grade is None:  # ADD-3
            lines.append(
                BreakdownLine(f"additives.{a.code}", "additives", 0, info, source,
                              note="Not rated: no EFSA overexposure assessment.")
            )  # fmt: skip
            continue
        penalty = cfg.risk_penalty[a.risk_level] * cfg.evidence_weight[a.evidence_grade]  # ADD-2
        total_penalty += penalty
        if a.risk_level == 3 and a.evidence_grade == "A":  # ADD-5
            cap_applies = True
        lines.append(
            BreakdownLine(f"additives.{a.code}", "additives", -round(penalty, 4), info, source,
                          note=f"EFSA: {RISK_WORDS[a.risk_level]}.")
        )  # fmt: skip

    value = max(0.0, 1.0 - total_penalty)  # ADD-1, ADD-7
    return AdditivesResult(True, round(value, 4), cap_applies, tuple(lines))
