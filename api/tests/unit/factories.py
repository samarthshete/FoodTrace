"""Small builders for scoring tests."""

from typing import Any

from app.scoring.types import AdditiveInfo, Nutrient, ProductFacts


def facts(
    *,
    tags: tuple[str, ...] = (),
    nova: int | None = None,
    additives: tuple[AdditiveInfo, ...] | None = (),
    estimated: tuple[str, ...] = (),
    **nutrients: float,
) -> ProductFacts:
    return ProductFacts(
        nutrients={k: Nutrient(v, k in estimated) for k, v in nutrients.items()},
        category_tags=tags,
        nova_group=nova,
        additives=additives,
    )


def additive(
    code: str, risk: int | None = None, grade: str | None = None, name: str | None = None
) -> AdditiveInfo:
    return AdditiveInfo(code=code, name=name or code.upper(), risk_level=risk, evidence_grade=grade)


# Worked example used across tests (general food):
# energy 1500 -> 4, sugars 12 -> 3, sat fat 2.5 -> 2, salt 0.9 -> 4  => A = 13
# A >= 11 so protein is not counted; fibre 4.5 -> 2, fvl 0 -> 0     => score 11, grade D
SNACK: dict[str, Any] = dict(energy_kj=1500, sugars_g=12, saturated_fat_g=2.5, salt_g=0.9,
             fiber_g=4.5, proteins_g=8, fvl_percent=0)  # fmt: skip
