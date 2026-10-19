import pytest

from app.services.explore import BY_ID, GROUPS, LIMIT_DEFAULT, LIMIT_MAX, clamp

spec = pytest.mark.spec
BANNED = ("toxic", "dangerous", "unsafe")


@spec("EXPLORE-1")
def test_ten_fixed_groups_in_order_with_unique_tags() -> None:
    assert [g.id for g in GROUPS] == ["breakfast", "yogurts", "breads", "snacks", "bars",
                                      "sweets", "drinks", "cheese", "meals", "spreads"]  # fmt: skip
    tags = [t for g in GROUPS for t in g.tags]
    assert len(tags) == len(set(tags)) and all(t.startswith("en:") for t in tags)
    assert BY_ID["cheese"].tags == ("en:cheeses",)
    for g in GROUPS:
        assert g.label and g.blurb.endswith(".") and not any(w in g.blurb.lower() for w in BANNED)


@spec("EXPLORE-2", "EXPLORE-5")
@pytest.mark.parametrize(
    ("given", "default", "maximum", "used"),
    [(None, 6, 24, 6), (3, 6, 24, 3), (0, 6, 24, 1), (-5, 6, 24, 1), (99, 6, 24, 24),
     (None, LIMIT_DEFAULT, LIMIT_MAX, 24), (500, LIMIT_DEFAULT, LIMIT_MAX, 60)],
)  # fmt: skip
def test_counts_default_and_are_clamped(
    given: int | None, default: int, maximum: int, used: int
) -> None:
    assert clamp(given, default, maximum) == used
