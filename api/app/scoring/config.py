"""Typed loader for config/scoring.yaml."""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Band(_Frozen):
    id: str
    label: str
    min: int


class ClassTags(_Frozen):
    water: list[str]
    water_exclude: list[str]
    beverage: list[str]
    beverage_exclude: list[str]
    cheese: list[str]
    cheese_exclude: list[str]
    fats_oils_nuts_seeds: list[str]
    fats_oils_nuts_seeds_exclude: list[str]


class GeneralTables(_Frozen):
    energy_kj: list[float]
    sugars_g: list[float]
    saturated_fat_g: list[float]
    salt_g: list[float]
    proteins_g: list[float]
    fiber_g: list[float]
    fvl_percent: list[tuple[float, int]]
    protein_cutoff_a_points: int
    red_meat_max_protein_points: int
    grades: dict[str, int]


class FatsTables(_Frozen):
    energy_from_saturates_kj: list[float]
    kj_per_g_saturates: float
    saturates_ratio_percent: list[float]
    protein_cutoff_a_points: int
    grades: dict[str, int]


class BeverageTables(_Frozen):
    energy_kj: list[float]
    sugars_g: list[float]
    proteins_g: list[float]
    fvl_percent: list[tuple[float, int]]
    sweeteners_points: int
    grades: dict[str, int]


class NutriScoreConfig(_Frozen):
    source_urls: dict[str, str]
    classes: ClassTags
    red_meat_tags: list[str]
    fvl_oil_tags: list[str]
    non_nutritive_sweeteners: list[str]
    general: GeneralTables
    fats_oils_nuts_seeds: FatsTables
    beverage: BeverageTables


class AdditivesConfig(_Frozen):
    risk_penalty: dict[int, float]
    evidence_weight: dict[str, float]
    cap_total: int
    efsa_source: str
    off_facet_url: str


class ProcessingConfig(_Frozen):
    source_url: str
    nova_values: dict[int, float]


class NovaEstimateConfig(_Frozen):
    ultra_markers: list[str]
    culinary: list[str]
    ignore: list[str]


class EstimatesConfig(_Frozen):
    source_url: str
    fvl_source_url: str
    fvl_words: list[str]
    fvl_exclude: list[str]
    nova: NovaEstimateConfig


class AlternativesConfig(_Frozen):
    min_gain: int
    limit: int
    min_confidence: float
    fallback_categories: int


class RecallsConfig(_Frozen):
    window_years: int
    limit: int
    generic_brands: list[str]
    stop_words: list[str]


class NutriScoreCap(_Frozen):
    grades: list[str]
    total: int


class ChangelogEntry(_Frozen):
    version: str
    change: str


class ScoringConfig(_Frozen):
    engine_version: str
    weights: dict[str, int]
    nutrition_anchors: dict[str, float]
    nutriscore_cap: NutriScoreCap
    bands: list[Band]
    nutriscore: NutriScoreConfig
    additives: AdditivesConfig
    processing: ProcessingConfig
    estimates: EstimatesConfig
    alternatives: AlternativesConfig
    recalls: RecallsConfig
    changelog: list[ChangelogEntry]


def load_config(path: Path = CONFIG_PATH) -> ScoringConfig:
    with path.open() as f:
        return ScoringConfig.model_validate(yaml.safe_load(f))


@lru_cache(maxsize=1)
def default_config() -> ScoringConfig:
    return load_config()
