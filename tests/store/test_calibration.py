from datetime import date
from fractions import Fraction

import pytest

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.calibration import InstrumentKind, SystemCheck
from starstamp.model.units import Expansion
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.db import Book

from ..support.factories import make_certificate, make_check


@pytest.fixture
def calibration(book: Book) -> CalibrationRepository:
    return CalibrationRepository(book.connection)


def test_certificates_round_trip(calibration: CalibrationRepository) -> None:
    calibration.add_certificate(make_certificate())
    found = calibration.certificates("wj-1")
    assert len(found) == 1
    assert found[0].instrument == InstrumentKind.CALIBRATED_CYLINDER
    assert found[0].valid_until == date(2029, 1, 15)


def test_certificates_are_scoped_to_their_system(calibration: CalibrationRepository) -> None:
    calibration.add_certificate(make_certificate())
    calibration.add_certificate(make_certificate(system_code="WJ-2"))
    assert len(calibration.certificates("WJ-1")) == 1
    assert calibration.systems() == ["WJ-1", "WJ-2"]


def test_in_force_filters_by_the_day(calibration: CalibrationRepository) -> None:
    calibration.add_certificate(make_certificate())
    calibration.add_certificate(
        make_certificate(
            InstrumentKind.PRESSURE_INDICATOR,
            serial="PG-4",
            issued_on=date(2020, 1, 1),
            valid_until=date(2023, 1, 1),
        )
    )
    assert len(calibration.in_force("WJ-1", date(2024, 6, 12))) == 1
    assert len(calibration.in_force("WJ-1", date(2022, 6, 12))) == 1
    assert len(calibration.in_force("WJ-1", date(2019, 6, 12))) == 0


def test_superseding_leaves_the_old_row_in_the_book(
    calibration: CalibrationRepository,
) -> None:
    first = calibration.add_certificate(make_certificate())
    calibration.supersede(first, "calibration house restated the expansion figure")
    assert calibration.certificates("WJ-1") == []
    assert len(calibration.certificates("WJ-1", standing_only=False)) == 1
    with pytest.raises(ConflictError, match="already superseded"):
        calibration.supersede(first, "again")


def test_superseding_something_that_is_not_there(calibration: CalibrationRepository) -> None:
    with pytest.raises(NotFoundError, match="no certificate 42"):
        calibration.supersede(42, "nothing")


def test_a_daily_check_round_trips(calibration: CalibrationRepository) -> None:
    calibration.record_check(make_check())
    found = calibration.check_on("WJ-1", date(2024, 6, 12))
    assert found is not None
    assert found.expected == Expansion(400)
    assert found.within_tolerance


def test_a_checks_tolerance_survives_the_round_trip(
    calibration: CalibrationRepository,
) -> None:
    calibration.record_check(make_check(tolerance_percent=Fraction(3, 2)))
    found = calibration.check_on("WJ-1", date(2024, 6, 12))
    assert found is not None
    assert found.tolerance_percent == Fraction(3, 2)


def test_only_one_check_a_day_a_system(calibration: CalibrationRepository) -> None:
    calibration.record_check(make_check())
    with pytest.raises(ConflictError, match="already has a check"):
        calibration.record_check(make_check(observed=Expansion(500)))
    calibration.record_check(make_check(system_code="WJ-2"))


def test_no_check_that_day(calibration: CalibrationRepository) -> None:
    assert calibration.check_on("WJ-1", date(2024, 6, 12)) is None


def test_checks_between(calibration: CalibrationRepository) -> None:
    for day in (date(2024, 6, 10), date(2024, 6, 11), date(2024, 6, 14)):
        calibration.record_check(make_check(day=day))
    found = calibration.checks_between("WJ-1", date(2024, 6, 10), date(2024, 6, 12))
    assert [check.day.day for check in found] == [10, 11]


def test_the_badge_that_ran_the_check_is_kept(calibration: CalibrationRepository) -> None:
    calibration.record_check(
        SystemCheck(
            system_code="WJ-1",
            day=date(2024, 6, 12),
            expected=Expansion(400),
            observed=Expansion(401),
            technician_badge="JT7",
        )
    )
    found = calibration.check_on("WJ-1", date(2024, 6, 12))
    assert found is not None
    assert found.technician_badge == "JT7"
