import pytest

from app.services.gtin import InvalidGTIN, check_digit_ok, lookup_forms, normalize

spec = pytest.mark.spec


@spec("GTIN-1")
@pytest.mark.parametrize("raw", ["0 36000 29145 2", "0-36000-29145-2", " 036000291452 "])
def test_strips_spaces_and_hyphens(raw: str) -> None:
    assert normalize(raw) == "0036000291452"


@spec("GTIN-1")
@pytest.mark.parametrize("raw", ["03600029145A", "036000.291452", "", "   "])
def test_rejects_non_digits(raw: str) -> None:
    with pytest.raises(InvalidGTIN):
        normalize(raw)


@spec("GTIN-2")
@pytest.mark.parametrize("raw", ["1234567", "123456789", "12345678901", "123456789012345"])
def test_rejects_bad_lengths(raw: str) -> None:
    with pytest.raises(InvalidGTIN, match="digits"):
        normalize(raw)


@spec("GTIN-3")
def test_upca_is_zero_padded() -> None:
    assert normalize("036000291452") == "0036000291452"


@spec("GTIN-3", "GTIN-6")
def test_ean8_is_zero_padded_not_expanded_as_upce() -> None:
    assert normalize("96385074") == "0000096385074"


@spec("GTIN-4")
def test_gtin14_with_leading_zero_is_reduced() -> None:
    assert normalize("00036000291452") == "0036000291452"


@spec("GTIN-4")
def test_gtin14_with_indicator_digit_is_rejected() -> None:
    assert check_digit_ok("10036000291459")  # valid GTIN-14, but a case code
    with pytest.raises(InvalidGTIN, match="case or pallet"):
        normalize("10036000291459")


@spec("GTIN-5")
@pytest.mark.parametrize("raw", ["036000291453", "0036000291451", "96385075"])
def test_rejects_wrong_check_digit(raw: str) -> None:
    with pytest.raises(InvalidGTIN, match="check digit"):
        normalize(raw)


@spec("GTIN-5")
@pytest.mark.parametrize("code", ["4006381333931", "5901234123457", "036000291452", "96385074"])
def test_check_digit_known_good_codes(code: str) -> None:
    assert check_digit_ok(code)


@spec("GTIN-7")
def test_invalid_gtin_has_readable_reason() -> None:
    with pytest.raises(InvalidGTIN) as exc:
        normalize("036000291453")
    assert "check digit" in str(exc.value)
    assert isinstance(exc.value, ValueError)


@spec("GTIN-8")
def test_lookup_forms_include_upca_for_leading_zero() -> None:
    assert lookup_forms("0036000291452") == ["0036000291452", "036000291452"]


@spec("GTIN-8")
def test_lookup_forms_ean13_only() -> None:
    assert lookup_forms("4006381333931") == ["4006381333931"]


@spec("GTIN-9")
@pytest.mark.parametrize("raw", ["036000291452", "96385074", "00036000291452", "4006381333931"])
def test_normalize_is_idempotent(raw: str) -> None:
    once = normalize(raw)
    assert normalize(once) == once
