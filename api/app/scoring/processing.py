"""NOVA processing, the P component (specs/004-processing.md)."""

from dataclasses import dataclass

from app.scoring.config import ProcessingConfig
from app.scoring.ingredients import NovaEstimate
from app.scoring.types import BreakdownLine

NOVA_LABELS = {1: "unprocessed or minimally processed", 2: "processed culinary ingredient",
               3: "processed food", 4: "ultra-processed food"}  # fmt: skip


@dataclass(frozen=True)
class ProcessingResult:
    known: bool
    value: float | None
    lines: tuple[BreakdownLine, ...]


def compute(
    nova_group: int | None, cfg: ProcessingConfig, estimate: NovaEstimate | None = None
) -> ProcessingResult:
    if nova_group not in cfg.nova_values:  # PROC-2, PROC-3
        if estimate is not None:
            return _estimated(estimate, cfg)  # EST-3, EST-4
        return ProcessingResult(False, None, ())
    value = cfg.nova_values[nova_group]  # PROC-1
    line = BreakdownLine(
        "processing.nova", "processing", value, nova_group, cfg.source_url,
        note=f"NOVA {nova_group}: {NOVA_LABELS[nova_group]}.",
    )  # fmt: skip
    return ProcessingResult(True, value, (line,))


def _estimated(estimate: NovaEstimate, cfg: ProcessingConfig) -> ProcessingResult:
    """A NOVA group derived from the ingredient list, flagged as estimated (EST-4)."""
    value = cfg.nova_values[estimate.group]
    why = f' ("{estimate.marker}")' if estimate.marker else ""
    note = (f"NOVA {estimate.group}: {NOVA_LABELS[estimate.group]}, "
            f"estimated from the ingredient list{why}.")  # fmt: skip
    line = BreakdownLine("processing.nova", "processing", value, estimate.group, cfg.source_url,
                         estimated=True, note=note)  # fmt: skip
    return ProcessingResult(True, value, (line,))
