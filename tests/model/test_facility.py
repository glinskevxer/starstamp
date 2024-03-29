from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.facility import Facility, Technician, normalise_badge, normalise_rin
from starstamp.model.method import Method

METHODS = frozenset({Method.VOLUMETRIC, Method.EXTERNAL_VISUAL})


def a_facility(**changes: object) -> Facility:
    base: dict[str, object] = {
        "rin": "A419",
        "name": "Wasatch Cylinder Service",
        "approved_from": date(2021, 5, 1),
        "approved_until": date(2026, 4, 30),
        "methods": METHODS,
    }
    base.update(changes)
    return Facility(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "expected"), [("a419", "A419"), (" AB1 ", "AB1"), ("A-419", "A419")]
)
def test_rin_normalises(text: str, expected: str) -> None:
    assert normalise_rin(text) == expected


@pytest.mark.parametrize("text", ["", "4A19", "A4", "A41999"])
def test_bad_rins(text: str) -> None:
    with pytest.raises(ValidationError, match="RIN is three or four"):
        normalise_rin(text)


def test_badges() -> None:
    assert normalise_badge(" jt7 ") == "JT7"
    with pytest.raises(ValidationError, match="two to eight"):
        normalise_badge("j")


def test_a_facility_approved_for_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="no methods at all"):
        a_facility(methods=frozenset())


def test_a_facility_cannot_expire_before_it_was_issued() -> None:
    with pytest.raises(ValidationError, match="cannot expire before"):
        a_facility(approved_until=date(2020, 1, 1))


def test_approval_window() -> None:
    facility = a_facility()
    assert not facility.approved_on(date(2021, 4, 30))
    assert facility.approved_on(date(2021, 5, 1))
    assert facility.approved_on(date(2026, 4, 30))
    assert not facility.approved_on(date(2026, 5, 1))


def test_may_perform_needs_both_the_method_and_the_day() -> None:
    facility = a_facility()
    assert facility.may_perform(Method.VOLUMETRIC, date(2024, 1, 1))
    assert not facility.may_perform(Method.ULTRASONIC, date(2024, 1, 1))
    assert not facility.may_perform(Method.VOLUMETRIC, date(2027, 1, 1))


def test_lapse_is_counted_in_days() -> None:
    facility = a_facility()
    assert facility.lapsed_by(date(2026, 4, 30)) == 0
    assert facility.lapsed_by(date(2026, 5, 3)) == 3


def test_a_technician_without_an_end_date_stays_qualified() -> None:
    technician = Technician(
        badge="JT7",
        name="Jesse Tovar",
        methods=METHODS,
        qualified_from=date(2022, 3, 1),
    )
    assert not technician.qualified_on(date(2022, 2, 28))
    assert technician.qualified_on(date(2030, 1, 1))
    assert technician.may_perform(Method.VOLUMETRIC, date(2030, 1, 1))


def test_a_lapsed_technician() -> None:
    technician = Technician(
        badge="JT7",
        name="Jesse Tovar",
        methods=METHODS,
        qualified_from=date(2022, 3, 1),
        qualified_until=date(2024, 3, 1),
    )
    assert technician.qualified_on(date(2024, 3, 1))
    assert not technician.qualified_on(date(2024, 3, 2))
    assert str(technician) == "JT7 Jesse Tovar"


def test_a_technician_signed_off_for_nothing() -> None:
    with pytest.raises(ValidationError, match="no methods"):
        Technician(badge="JT7", name="x", methods=frozenset(), qualified_from=date(2022, 3, 1))


def test_a_technician_cannot_lapse_before_being_signed_off() -> None:
    with pytest.raises(ValidationError, match="cannot lapse before"):
        Technician(
            badge="JT7",
            name="x",
            methods=METHODS,
            qualified_from=date(2022, 3, 1),
            qualified_until=date(2021, 1, 1),
        )


def test_facility_text() -> None:
    assert str(a_facility()) == "A419 Wasatch Cylinder Service"
