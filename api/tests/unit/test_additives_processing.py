import pytest

from app.scoring import additives, processing
from app.scoring.config import default_config

from .factories import additive

spec = pytest.mark.spec
ADD = default_config().additives
PROC = default_config().processing


# --- Additives (spec 003) ---


@spec("ADD-1", "ADD-2")
def test_penalty_is_risk_times_evidence() -> None:
    r = additives.compute((additive("e250", 2, "B"), additive("e330", 1, "C")), ADD)
    expected = 1 - (0.15 * 0.6 + 0.05 * 0.3)
    assert r.value == pytest.approx(expected, abs=1e-4)


@spec("ADD-1")
def test_value_never_below_zero() -> None:
    many = tuple(additive(f"e{100 + i}", 3, "A") for i in range(5))
    assert additives.compute(many, ADD).value == 0.0


@spec("ADD-3")
def test_unrated_additive_gives_no_penalty_but_is_listed() -> None:
    r = additives.compute((additive("e330"),), ADD)
    assert r.value == 1.0
    [line] = r.lines
    assert line.points == 0 and line.note and "Not rated" in line.note


@spec("ADD-4")
def test_duplicates_counted_once() -> None:
    once = additives.compute((additive("e250", 2, "A"),), ADD)
    twice = additives.compute((additive("e250", 2, "A"), additive("e250", 2, "A")), ADD)
    assert once.value == twice.value and len(twice.lines) == 1


@spec("ADD-5")
def test_cap_needs_high_risk_and_strong_evidence() -> None:
    assert additives.compute((additive("e250", 3, "A"),), ADD).cap_applies
    assert not additives.compute((additive("e250", 3, "B"),), ADD).cap_applies
    assert not additives.compute((additive("e250", 2, "A"),), ADD).cap_applies


@spec("ADD-6")
def test_unknown_additive_list_is_unknown_not_perfect() -> None:
    r = additives.compute(None, ADD)
    assert not r.known and r.value is None


@spec("ADD-7")
def test_known_empty_list_is_perfect() -> None:
    r = additives.compute((), ADD)
    assert r.known and r.value == 1.0


@spec("ADD-8")
def test_line_rule_id_and_source() -> None:
    r = additives.compute((additive("e250", 2, "B"),), ADD)
    [line] = r.lines
    assert line.rule_id == "additives.e250"
    assert line.source_url == "https://world.openfoodfacts.org/facets/additives/e250"


# --- Processing (spec 004) ---


@spec("PROC-1")
@pytest.mark.parametrize(("nova", "value"), [(1, 1.0), (2, 0.67), (3, 0.33), (4, 0.0)])
def test_nova_mapping(nova: int, value: float) -> None:
    assert processing.compute(nova, PROC).value == value


@spec("PROC-2", "PROC-3")
@pytest.mark.parametrize("nova", [None, 0, 5, -1])
def test_missing_or_invalid_nova_is_unknown(nova: int | None) -> None:
    r = processing.compute(nova, PROC)
    assert not r.known and r.value is None and r.lines == ()


@spec("PROC-4")
def test_nova_line() -> None:
    [line] = processing.compute(4, PROC).lines
    assert line.rule_id == "processing.nova"
    assert line.input_value == 4
    assert line.source_url == "https://world.openfoodfacts.org/nova"
