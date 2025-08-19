"""A shop with two rigs and two people, which is where the seams show.

Everything else in the suite runs a shop with one of each, and one of each
hides the interesting failures: capacity that does not follow the rig that is
actually in date, work booked against a person who cannot do it, a day where
one rig is out and the other is not.
"""

from __future__ import annotations

from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.calibration import InstrumentKind
from starstamp.model.cylinder import CylinderKey
from starstamp.model.method import Method
from starstamp.model.specification import parse_specification
from starstamp.model.units import Pressure
from starstamp.service.requalify import RequalificationService
from starstamp.service.schedule import ScheduleService
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.db import Book
from starstamp.store.facility import TechnicianRepository

from ..support.factories import (
    make_certificate,
    make_check,
    make_cylinder,
    make_readings,
    make_technician,
)
from ..support.requests import make_request
from ..support.shop import DAY, stock

FIRST = CylinderKey("NCI", "A4471")
SECOND = CylinderKey("LUX", "AL9")


@pytest.fixture
def two_rigs(shop_book: Book) -> Book:
    """A second rig, and a second person who can only do half the work."""
    calibration = CalibrationRepository(shop_book.connection)
    for instrument in InstrumentKind.ALL:
        calibration.add_certificate(
            make_certificate(instrument, system_code="WJ-2", serial=f"{instrument[:3]}-2")
        )
    calibration.record_check(make_check(system_code="WJ-2"))
    TechnicianRepository(shop_book.connection).add(
        make_technician(
            badge="MR2",
            name="Marisol Reyes",
            methods=frozenset({Method.ULTRASONIC, Method.EXTERNAL_VISUAL}),
        )
    )
    stock(
        shop_book,
        make_cylinder(
            key=SECOND,
            specification=parse_specification("DOT-3AL3000"),
            nominal_wall_thousandths_in=220,
            wall_source="data sheet",
        ),
    )
    return shop_book


def test_the_capacity_counts_both_rigs(two_rigs: Book) -> None:
    service = ScheduleService(two_rigs)
    assert sorted(service.working_rigs(DAY)) == ["WJ-1", "WJ-2"]
    assert service.capacity(DAY).capacity == 48


def test_a_rig_out_of_date_takes_its_own_capacity_only(two_rigs: Book) -> None:
    two_rigs.connection.execute(
        "UPDATE calibration_certificate SET valid_until = '2024-06-01'"
        " WHERE system_code = 'WJ-2' AND instrument = 'pressure_indicator'"
    )
    service = ScheduleService(two_rigs)
    assert service.working_rigs(DAY) == ["WJ-1"]
    assert service.capacity(DAY).capacity == 24


def test_each_person_is_held_to_their_own_sign_off(two_rigs: Book) -> None:
    service = RequalificationService(two_rigs)
    with pytest.raises(RuleViolationError, match="MR2 is not signed off for volumetric"):
        service.perform(make_request(technician_badge="MR2"))
    result = service.perform(make_request(technician_badge="JT7"))
    assert result.outcome.may_be_marked


def test_the_second_rig_does_the_work_the_first_cannot(two_rigs: Book) -> None:
    from starstamp.model.ultrasonic import Position, Reading, Scan

    scan = Scan(
        tuple(Reading(Position.parse(name), 215) for name in ("S1", "U1", "U2", "M1", "M2", "L1"))
    )
    result = RequalificationService(two_rigs).perform(
        make_request(
            key=SECOND,
            technician_badge="MR2",
            method=Method.ULTRASONIC,
            system_code="WJ-2",
            with_readings=False,
            scan=scan,
        )
    )
    assert result.outcome.may_be_marked
    assert result.scan is not None
    assert not result.star.granted


def test_the_check_on_one_rig_does_not_cover_the_other(two_rigs: Book) -> None:
    two_rigs.connection.execute("DELETE FROM system_check WHERE system_code = 'WJ-1'")
    service = RequalificationService(two_rigs)
    with pytest.raises(RuleViolationError, match="no start of day check"):
        service.perform(make_request())
    result = service.perform(make_request(system_code="WJ-2"))
    assert result.outcome.may_be_marked


def test_work_on_both_rigs_reads_back_separately(two_rigs: Book) -> None:
    from starstamp.reporting import rig

    service = RequalificationService(two_rigs)
    service.perform(make_request())
    service.perform(
        make_request(
            key=SECOND,
            system_code="WJ-2",
            readings=make_readings(applied=Pressure(5000)),
        )
    )
    standings = {
        item.system_code: item
        for item in rig.build_all(two_rigs, date(2024, 6, 1), date(2024, 6, 30))
    }
    assert standings["WJ-1"].tested == 1
    assert standings["WJ-2"].tested == 1


def test_booking_fills_the_shop_not_one_rig(two_rigs: Book) -> None:
    service = ScheduleService(two_rigs)
    service.book_in("WELD1", DAY, 40, date(2024, 6, 3))
    standing = service.capacity(DAY)
    assert standing.free == 8
    with pytest.raises(RuleViolationError, match="room for 8 more"):
        service.book_in("WELD1", DAY, 9, date(2024, 6, 3))
