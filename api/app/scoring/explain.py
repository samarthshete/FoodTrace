"""Plain-language summary ("In short") from a score breakdown (ENGINE-12, ENGINE-13, ENGINE-15).

Templates only, no LLM. The first sentence is the verdict; each following sentence gives one
reason, in a fixed order: nutrition, its main nutrients, additives, processing, data gaps.
"""

from app.scoring import nutriscore_2023
from app.scoring.config import default_config
from app.scoring.engine import ScoreResult
from app.scoring.types import BreakdownLine

CLASS_LABELS = {"general": "general food", "cheese": "cheese", "beverage": "drink",
                "fats_oils_nuts_seeds": "fat, oil, nut or seed", "water": "water"}  # fmt: skip
GRADE_WORDS = {"a": "very good", "b": "good", "c": "average", "d": "poor", "e": "very poor"}
NUTRIENT_LABELS = {
    "energy": ("energy", "kJ"),
    "energy_from_saturates": ("energy from saturated fat", "kJ"),
    "sugars": ("sugars", "g"),
    "saturated_fat": ("saturated fat", "g"),
    "saturates_ratio": ("saturated fat", "% of its fat"),
    "salt": ("salt", "g"),
    "proteins": ("protein", "g"),
    "fiber": ("fibre", "g"),
    "fvl": ("fruit, vegetables and legumes", "%"),
}
FIELD_LABELS = {"energy_kj": "energy", "sugars_g": "sugars", "saturated_fat_g": "saturated fat",
                "fat_g": "fat", "salt_g": "salt", "fiber_g": "fibre", "proteins_g": "protein",
                "fvl_percent": "fruit/vegetable share", "nova_group": "processing level",
                "additives": "ingredient list"}  # fmt: skip
NOVA_WORDS = {1: "Unprocessed or minimally processed", 2: "A processed culinary ingredient",
              3: "Processed", 4: "Ultra-processed"}  # fmt: skip


def _nutrient(line: BreakdownLine) -> tuple[str, str]:
    key = line.rule_id.rsplit(".", 1)[-1]
    return NUTRIENT_LABELS.get(key, (key, ""))


def display_number(value: float, unit: str) -> str:
    """Rounded for reading (ENGINE-13): kJ whole; g and % to 1 decimal, or 2 below 1."""
    digits = 0 if unit == "kJ" else 2 if abs(value) < 1 else 1
    text = f"{value:.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _fmt(value: object, unit: str) -> str:
    if isinstance(value, int | float) and not isinstance(value, bool):
        value = display_number(float(value), unit)
    if unit.startswith("%"):
        return f"{value}{unit}"
    return f"{value} {unit}".strip()


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _nutrients(result: ScoreResult, per: str) -> list[str]:
    """ "High in …" / "Good source of …" for components at half their maximum or more."""
    ns = result.nutriscore
    if ns["class"] == "water" or ns["score"] is None:
        return []
    most = nutriscore_2023.max_points(ns["class"], default_config().nutriscore)
    lines = [ln for ln in result.breakdown if ln.rule_id.startswith("nutriscore.")]

    def strong(ln: BreakdownLine) -> bool:
        key = ln.rule_id.rsplit(".", 1)[-1]
        return key in most and abs(ln.points) * 2 >= most[key] and ln.points != 0

    def phrase(ln: BreakdownLine) -> str:
        label, unit = _nutrient(ln)
        return f"{label} ({_fmt(ln.input_value, unit)})"

    high = sorted((ln for ln in lines if ln.points > 0 and strong(ln)), key=lambda ln: -ln.points)
    good = sorted((ln for ln in lines if ln.points < 0 and strong(ln)), key=lambda ln: ln.points)
    out = []
    if high:
        out.append(f"High in {_join([phrase(ln) for ln in high[:2]])} {per}.")
    if good:
        out.append(f"Good source of {_join([phrase(ln) for ln in good[:2]])} {per}.")
    return out


def _additives(result: ScoreResult) -> str | None:
    lines = [ln for ln in result.breakdown if ln.component == "additives"
             and ln.rule_id.startswith("additives.") and ln.rule_id != "additives.cap"]  # fmt: skip
    if not result.components["additives"]["known"]:
        return "Additives unknown: no ingredient list."
    if not lines:
        return "No additives."
    names = [str(ln.input_value["name"]) for ln in lines if isinstance(ln.input_value, dict)]
    if any(ln.rule_id == "additives.cap" for ln in result.breakdown):
        worst = [n for ln, n in zip(lines, names, strict=False) if ln.points <= -0.4]
        who = _join(worst or names[:1])
        return f"{who} has a high EFSA overexposure rating, so the score is capped."
    rated = [n for ln, n in zip(lines, names, strict=False) if ln.points < 0]
    if rated:
        return f"Additives with an EFSA risk rating lower the score: {_join(rated)}."
    count = len(lines)
    return f"{count} {'additive' if count == 1 else 'additives'}, none with an EFSA risk rating."


def _processing(result: ScoreResult) -> str | None:
    line = next((ln for ln in result.breakdown if ln.rule_id == "processing.nova"), None)
    if line is None or not isinstance(line.input_value, int):
        return None
    words = NOVA_WORDS.get(line.input_value, f"NOVA {line.input_value}")
    flag = ", estimated from the ingredient list" if line.estimated else ""
    return f"{words} (NOVA {line.input_value}{flag})."


def explain(result: ScoreResult) -> list[str]:
    out: list[str] = []
    ns = result.nutriscore
    missing = [FIELD_LABELS.get(m, m) for m in result.missing_inputs]
    if result.status == "not_scored":
        out.append(f"Not scored: the label data is missing {', '.join(missing)}.")
    else:
        assert result.band is not None
        verdict = f"Scores {result.total} out of 100 ({result.band['label']})."
        cap = next((ln for ln in result.breakdown if ln.rule_id == "nutrition.cap"), None)
        if cap is not None and ns["grade"]:
            verdict += (
                f" Capped at {cap.input_value} because its Nutri-Score is {ns['grade'].upper()}."
            )
        out.append(verdict)

    if ns["grade"]:
        word = GRADE_WORDS[ns["grade"]]
        out.append(f"Nutrition: {word} (Nutri-Score {ns['grade'].upper()}, scored as a "
                   f"{CLASS_LABELS[ns['class']]}).")  # fmt: skip
    per = "per 100 ml" if ns["class"] == "beverage" else "per 100 g"
    out.extend(_nutrients(result, per))

    if (additives := _additives(result)) is not None:
        out.append(additives)
    if (processing := _processing(result)) is not None:
        out.append(processing)

    nutrition = [ln for ln in result.breakdown if ln.rule_id.startswith("nutriscore.")]
    estimated = sorted({_nutrient(ln)[0] for ln in nutrition if ln.estimated})
    # An estimated processing level is already flagged in its own sentence (EST-7).
    if estimated:
        out.append(f"Estimated from the ingredient list: {', '.join(estimated)}.")
    if missing and result.status == "scored":
        out.append(f"Some data is missing ({', '.join(missing)}), so this score is less certain.")
    return out
