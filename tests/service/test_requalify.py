from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.calibration import InstrumentKind
from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import DefectKind
from starstamp.model.event import Outcome
from starstamp.model.method import Method
from starstamp.model.units import Expansion
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book

from ..support.factories import make_check, make_observation, make_readings
from ..support.shop import DAY, SYSTEM, a_wet_cylinder

KEY = CylinderKey("NCI", "A4471")


def a_request(**changes: object) -> RequalificationRequest:
    base: dict[str, object] = {
        "key": KEY,
        "day": DAY,
        "technician_badge": "JT7",
        "method": Method.VOLUMETRIC,
        "system_code": SYSTEM,
        "readings": make_readings(),
    }
    base.update(changes)
    return RequalificationRequest(**base)  # type: ignore[arg-type]


def test_a_clean_run_passes_and_is_written_down(shop_book: Book) -> None:
    result = RequalificationService(shop_book).perform(a_request())
    assert result.outcome is Outcome.PASS
    assert result.due == StampedMonth(2034, 6)
    assert result.star.granted
    assert result.plus.granted
    assert result.event.event_id is not None
    assert "starred" in result.summary()


def test_the_event_survives_in_the_book(shop_book: Book) -> None:
    service = RequalificationService(shop_book)
    service.perform(a_request())
    history = service.events.for_cylinder(KEY)
    assert len(history) == 1
    assert history[0].method is Method.VOLUMETRIC


def test_a_stretched_cylinder_is_condemned_and_the_status_follows(shop_book: Book) -> None:
    stretched = make_readings(
        total_expansion=Expansion.parse("100.0"), permanent_expansion=Expansion.parse("11.0")
    )
    result = RequalificationService(shop_book).perform(a_request(readings=stretched))
    assert result.outcome is Outcome.CONDEMN
    assert result.due is None
    assert CylinderRepository(shop_book.connection).by_key(KEY).status is CylinderStatus.CONDEMNED


def test_a_condemning_visual_keeps_the_cylinder_off_the_rig(shop_book: Book) -> None:
    result = RequalificationService(shop_book).perform(
        a_request(observations=(make_observation(DefectKind.BULGE),))
    )
    assert result.outcome is Outcome.CONDEMN
    assert result.pressure is None
    assert "bulge" in result.event.reasons[0]


def test_a_repairable_finding_suspends_the_cylinder(shop_book: Book) -> None:
    result = RequalificationService(shop_book).perform(
        a_request(observations=(make_observation(DefectKind.THREAD_DAMAGE),))
    )
    assert result.outcome is Outcome.SUSPENDED
    assert result.pressure is None
    status = CylinderRepository(shop_book.connection).by_key(KEY).status
    assert status is CylinderStatus.AWAITING_REPAIR


def test_a_lapsed_certificate_stops_the_event_being_written(shop_book: Book) -> None:
    service = RequalificationService(shop_book)
    shop_book.connection.execute(
        "UPDATE calibration_certificate SET valid_until = '2024-06-01' WHERE instrument = ?",
        (InstrumentKind.EXPANSION_SCALE,),
    )
    with pytest.raises(RuleViolationError, match="not fit to requalify"):
        service.perform(a_request())
    assert service.events.for_cylinder(KEY) == []


def test_a_day_with_no_start_of_day_check(shop_book: Book) -> None:
    service = RequalificationService(shop_book)
    with pytest.raises(RuleViolationError, match="no start of day check"):
        service.perform(a_request(day=date(2024, 6, 13)))


def test_a_method_the_cylinder_does_not_take(shop_book: Book) -> None:
    service = RequalificationService(shop_book)
    with pytest.raises(RuleViolationError, match="not permitted"):
        service.perform(a_request(method=Method.PROOF_PRESSURE, readings=None))


def test_the_method_is_chosen_when_none_is_named(shop_book: Book) -> None:
    result = RequalificationService(shop_book).perform(a_request(method=None))
    assert result.event.method is Method.VOLUMETRIC


def test_a_pressure_test_without_readings_is_refused(shop_book: Book) -> None:
    service = RequalificationService(shop_book)
    with pytest.raises(RuleViolationError, match="needs the rig's readings"):
        service.perform(a_request(readings=None))


def test_a_second_requalification_reads_the_first_for_the_star(shop_book: Book) -> None:
    service = RequalificationService(shop_book)
    service.perform(a_request())
    later = service.perform(a_request(day=date(2024, 6, 12)))
    assert later.star.granted


def test_work_stops_when_the_shop_own_number_lapses(shop_book: Book) -> None:
    service = RequalificationService(shop_book)
    service.calibration.record_check(make_check(day=date(2026, 5, 4)))
    with pytest.raises(RuleViolationError, match="A419 is lapsed 4 days ago"):
        service.perform(a_request(day=date(2026, 5, 4)))
    assert service.events.for_cylinder(KEY) == []


def test_a_welded_cylinder_in_a_dedicated_service_takes_the_visual(shop_book: Book) -> None:
    key = a_wet_cylinder(shop_book, CylinderKey("PST", "LP770"))
    result = RequalificationService(shop_book).perform(
        a_request(
            key=key,
            method=Method.EXTERNAL_VISUAL,
            readings=None,
            system_code=None,
            observations=(make_observation(DefectKind.INTERIOR_CORROSION, depth_thousandths_in=4),),
        )
    )
    assert result.outcome is Outcome.PASS
    assert result.due == StampedMonth(2029, 6)
    assert not result.star.granted
