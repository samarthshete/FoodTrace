import pytest

from app.services.alternatives import candidate_categories

spec = pytest.mark.spec
CATS = ["en:foods", "en:snacks", "en:sweet-snacks", "en:cereal-bars"]


@spec("ALT-4")
def test_primary_first_then_two_less_specific() -> None:
    assert candidate_categories("en:cereal-bars", CATS, 2) == [
        "en:cereal-bars",
        "en:sweet-snacks",
        "en:snacks",
    ]


@spec("ALT-4")
def test_never_goes_broader_than_the_fallback_count() -> None:
    assert "en:foods" not in candidate_categories("en:cereal-bars", CATS, 2)


@spec("ALT-4")
def test_primary_in_the_middle_only_walks_towards_general() -> None:
    assert candidate_categories("en:snacks", CATS, 2) == ["en:snacks", "en:foods"]


@spec("ALT-8")
def test_no_primary_category_means_no_candidates() -> None:
    assert candidate_categories(None, CATS, 2) == []
