from datetime import date
from fractions import Fraction

import pytest

from starstamp.errors import ValidationError
from starstamp.model.calibration import InstrumentKind, SystemCheck, normalise_system_code
from starstamp.model.units import Expansion

from ..support.factories import make_certificate


def test_system_codes() -> None:
    assert normalise_system_code(" wj 1 ") == "WJ-1"
    with pytest.raises(ValidationError, match="2 to 12"):
        normalise_system_code("W")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("gauge", InstrumentKind.PRESSURE_INDICATOR),
        ("transducer", InstrumentKind.PRESSURE_INDICATOR),
        ("burette", InstrumentKind.EXPANSION_SCALE),
        ("calibrated cylinder", InstrumentKind.CALIBRATED_CYLINDER),
    ],
)
def test_instrument_shorthand(text: str, expected: str) -> None:
    assert InstrumentKind.parse(text) == expected


def test_unknown_instrument() -> None:
    with pytest.raises(ValidationError, match="unknown instrument"):
        InstrumentKind.parse("thermometer")


def test_certificate_window() -> None:
    certificate = make_certificate()
    assert not certificate.valid_on(date(2024, 1, 14))
    assert certificate.valid_on(date(2024, 1, 15))
    assert certificate.valid_on(date(2029, 1, 15))
    assert not certificate.valid_on(date(2029, 1, 16))


def test_days_left_goes_negative_after_expiry() -> None:
    certificate = make_certificate()
    assert certificate.days_left(date(2029, 1, 10)) == 5
    assert certificate.days_left(date(2029, 1, 20)) == -5


def test_a_certificate_that_expires_before_issue() -> None:
    with pytest.raises(ValidationError, match="expires before"):
        make_certificate(valid_until=date(2023, 1, 1))


def test_a_certificate_without_a_serial() -> None:
    with pytest.raises(ValidationError, match="name the instrument"):
        make_certificate(serial="   ")


def test_a_check_dead_on_expected_passes() -> None:
    check = SystemCheck(
        system_code="WJ-1",
        day=date(2024, 6, 12),
        expected=Expansion.parse("40.0"),
        observed=Expansion.parse("40.0"),
    )
    assert check.deviation == 0
    assert check.within_tolerance


def test_a_check_one_percent_low_is_on_the_line() -> None:
    check = SystemCheck(
        system_code="WJ-1",
        day=date(2024, 6, 12),
        expected=Expansion.parse("40.0"),
        observed=Expansion.parse("39.6"),
    )
    assert check.deviation == Fraction(-1)
    assert check.within_tolerance


def test_a_check_past_tolerance_fails() -> None:
    check = SystemCheck(
        system_code="WJ-1",
        day=date(2024, 6, 12),
        expected=Expansion.parse("40.0"),
        observed=Expansion.parse("39.5"),
    )
    assert not check.within_tolerance
    assert "-1.25%" in check.describe()


def test_a_wider_tolerance_accepts_it() -> None:
    check = SystemCheck(
        system_code="WJ-1",
        day=date(2024, 6, 12),
        expected=Expansion.parse("40.0"),
        observed=Expansion.parse("39.5"),
        tolerance_percent=Fraction(3, 2),
    )
    assert check.within_tolerance


def test_the_deviation_is_exact() -> None:
    check = SystemCheck(
        system_code="WJ-1",
        day=date(2024, 6, 12),
        expected=Expansion.parse("30.0"),
        observed=Expansion.parse("30.1"),
    )
    assert check.deviation == Fraction(1, 3)


def test_a_check_against_nothing() -> None:
    with pytest.raises(ValidationError, match="cannot be zero"):
        SystemCheck(
            system_code="WJ-1",
            day=date(2024, 6, 12),
            expected=Expansion(0),
            observed=Expansion.parse("1.0"),
        )


def test_a_tolerance_of_zero() -> None:
    with pytest.raises(ValidationError, match="passes nothing"):
        SystemCheck(
            system_code="WJ-1",
            day=date(2024, 6, 12),
            expected=Expansion.parse("40.0"),
            observed=Expansion.parse("40.0"),
            tolerance_percent=Fraction(0),
        )


def test_certificate_text() -> None:
    assert str(make_certificate()).startswith("WJ-1 calibrated_cylinder CC-88012")
