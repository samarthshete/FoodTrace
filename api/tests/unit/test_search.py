import pytest

from app.services.search import clamp_limit, words

spec = pytest.mark.spec


@spec("SEARCH-5")
def test_query_words_are_ascii_letters_and_digits_only() -> None:
    assert words("Ben & Jerry's  Café-Crème!") == ["ben", "jerry", "s", "cafe", "creme"]
    assert words("oat:* | !milk") == ["oat", "milk"]  # tsquery operators can't leak through
    assert words("&&&") == []


@spec("SEARCH-1")
@pytest.mark.parametrize(("given", "used"), [(None, 10), (5, 5), (0, 1), (-3, 1), (99, 25)])
def test_limit_defaults_to_10_and_is_clamped(given: int | None, used: int) -> None:
    assert clamp_limit(given) == used
