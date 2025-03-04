from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.acetylene import AcetyleneExam
from starstamp.model.calibration import InstrumentKind
from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import DefectKind
from starstamp.model.event import Outcome
from starstamp.model.method import Method
from starstamp.model.ultrasonic import Position, Reading, Scan
from starstamp.model.units import Expansion
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book

from ..support.factories import make_check, make_observation, make_readings
from ..support.shop import DAY, SYSTEM, a_wet_cylinder

KEY = CylinderKey("NCI", "A4471")


def _a_scan(value: int, thin: tuple[str, int] | None = None) -> Scan:
    points = [
        ("S1", value),
        ("U1", value),
        ("U2", value),
        ("M1", value),
        ("M2", value),
        ("L1", value),
    ]
    if thin is not None:
        points = [thin if name == thin[0] else (name, reading) for name, reading in points]
    return Scan(tuple(Reading(Position.parse(name), reading) for name, reading in points))


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


def test_an_ultrasonic_examination_passes(shop_book: Book) -> None:
    from starstamp.model.specification import parse_specification

    from ..support.factories import make_cylinder
    from ..support.shop import stock

    key = stock(
        shop_book,
        make_cylinder(
            key=CylinderKey("LUX", "AL9"),
            specification=parse_specification("DOT-3AL3000"),
            nominal_wall_thousandths_in=220,
            wall_source="data sheet",
        ),
    )
    scan = _a_scan(215)
    result = RequalificationService(shop_book).perform(
        a_request(key=key, method=Method.ULTRASONIC, readings=None, scan=scan)
    )
    assert result.outcome is Outcome.PASS
    assert result.scan is not None
    assert result.scan.passed
    assert not result.star.granted


def test_a_thin_spot_condemns_through_the_service(shop_book: Book) -> None:
    from starstamp.model.specification import parse_specification

    from ..support.factories import make_cylinder
    from ..support.shop import stock

    key = stock(
        shop_book,
        make_cylinder(
            key=CylinderKey("LUX", "AL9"),
            specification=parse_specification("DOT-3AL3000"),
            nominal_wall_thousandths_in=220,
            wall_source="data sheet",
        ),
    )
    scan = _a_scan(215, thin=("U2", 190))
    result = RequalificationService(shop_book).perform(
        a_request(key=key, method=Method.ULTRASONIC, readings=None, scan=scan)
    )
    assert result.outcome is Outcome.CONDEMN
    assert "design minimum" in result.event.reasons[0]


def test_a_scan_handed_to_a_water_jacket_test(shop_book: Book) -> None:
    with pytest.raises(RuleViolationError, match="takes no ultrasonic readings"):
        RequalificationService(shop_book).perform(a_request(scan=_a_scan(215)))


def test_an_ultrasonic_method_with_no_scan(shop_book: Book) -> None:
    from starstamp.model.specification import parse_specification

    from ..support.factories import make_cylinder
    from ..support.shop import stock

    key = stock(
        shop_book,
        make_cylinder(
            key=CylinderKey("LUX", "AL9"),
            specification=parse_specification("DOT-3AL3000"),
            nominal_wall_thousandths_in=220,
            wall_source="data sheet",
        ),
    )
    with pytest.raises(RuleViolationError, match="needs its readings"):
        RequalificationService(shop_book).perform(
            a_request(key=key, method=Method.ULTRASONIC, readings=None)
        )


def test_the_scan_is_kept_beside_the_record(shop_book: Book) -> None:
    from starstamp.model.specification import parse_specification

    from ..support.factories import make_cylinder
    from ..support.shop import stock

    key = stock(
        shop_book,
        make_cylinder(
            key=CylinderKey("LUX", "AL9"),
            specification=parse_specification("DOT-3AL3000"),
            nominal_wall_thousandths_in=220,
            wall_source="data sheet",
        ),
    )
    service = RequalificationService(shop_book)
    result = service.perform(
        a_request(key=key, method=Method.ULTRASONIC, readings=None, scan=_a_scan(215))
    )
    assert result.event.event_id is not None
    stored = service.events.scan_for(result.event.event_id)
    assert stored.count == 6
    assert stored.thinnest.thousandths_in == 215


def an_acetylene_cylinder(book: Book) -> CylinderKey:
    from starstamp.model.service import ACETYLENE
    from starstamp.model.specification import parse_specification

    from ..support.factories import make_cylinder
    from ..support.shop import stock

    return stock(
        book,
        make_cylinder(
            key=CylinderKey("PST", "AC7"),
            specification=parse_specification("DOT-8AL"),
            service=ACETYLENE,
            rejection_elastic_expansion=None,
            tare_hundredths_lb=8500,
            valve_outlet="510",
        ),
    )


def test_an_acetylene_cylinder_that_holds_its_weight_passes(shop_book: Book) -> None:
    key = an_acetylene_cylinder(shop_book)
    result = RequalificationService(shop_book).perform(
        a_request(
            key=key,
            method=Method.ACETYLENE_VISUAL,
            readings=None,
            system_code=None,
            acetylene=AcetyleneExam(tare_now_hundredths_lb=8470),
        )
    )
    assert result.outcome is Outcome.PASS
    assert result.acetylene is not None
    assert result.due == StampedMonth(2034, 6)


def test_a_light_acetylene_cylinder_is_condemned(shop_book: Book) -> None:
    key = an_acetylene_cylinder(shop_book)
    result = RequalificationService(shop_book).perform(
        a_request(
            key=key,
            method=Method.ACETYLENE_VISUAL,
            readings=None,
            system_code=None,
            acetylene=AcetyleneExam(tare_now_hundredths_lb=8000),
        )
    )
    assert result.outcome is Outcome.CONDEMN
    assert "against its marked tare" in result.event.reasons[0]


def test_bad_plugs_suspend_the_acetylene_cylinder(shop_book: Book) -> None:
    key = an_acetylene_cylinder(shop_book)
    result = RequalificationService(shop_book).perform(
        a_request(
            key=key,
            method=Method.ACETYLENE_VISUAL,
            readings=None,
            system_code=None,
            acetylene=AcetyleneExam(tare_now_hundredths_lb=8470, fuse_plugs_sound=False),
        )
    )
    assert result.outcome is Outcome.SUSPENDED
    assert "fusible plugs" in result.event.reasons[0]


def test_the_weighing_is_kept(shop_book: Book) -> None:
    key = an_acetylene_cylinder(shop_book)
    service = RequalificationService(shop_book)
    result = service.perform(
        a_request(
            key=key,
            method=Method.ACETYLENE_VISUAL,
            readings=None,
            system_code=None,
            acetylene=AcetyleneExam(tare_now_hundredths_lb=8470, note="scale 2"),
        )
    )
    assert result.event.event_id is not None
    stored = service.events.acetylene_exam(result.event.event_id)
    assert stored is not None
    assert stored.tare_now_hundredths_lb == 8470
    assert stored.note == "scale 2"


def test_a_weighing_handed_to_a_water_jacket_test(shop_book: Book) -> None:
    with pytest.raises(RuleViolationError, match="does not weigh the cylinder"):
        RequalificationService(shop_book).perform(
            a_request(acetylene=AcetyleneExam(tare_now_hundredths_lb=8470))
        )


def test_an_acetylene_examination_with_no_weighing(shop_book: Book) -> None:
    key = an_acetylene_cylinder(shop_book)
    with pytest.raises(RuleViolationError, match="needs the cylinder weighed"):
        RequalificationService(shop_book).perform(
            a_request(key=key, method=Method.ACETYLENE_VISUAL, readings=None, system_code=None)
        )


def test_the_shop_can_hold_longer_than_the_regulation(shop_book: Book) -> None:
    from starstamp.model.settings import MINIMUM_HOLD
    from starstamp.store.settings import SettingRepository

    SettingRepository(shop_book.connection).set(MINIMUM_HOLD, "60", date(2024, 1, 1))
    with pytest.raises(RuleViolationError, match="short of the 60s"):
        RequalificationService(shop_book).perform(
            a_request(readings=make_readings(hold_seconds=45))
        )


def test_a_longer_hold_only_applies_from_the_day_it_was_set(shop_book: Book) -> None:
    from starstamp.model.settings import MINIMUM_HOLD
    from starstamp.store.settings import SettingRepository

    SettingRepository(shop_book.connection).set(MINIMUM_HOLD, "60", date(2025, 1, 1))
    result = RequalificationService(shop_book).perform(
        a_request(readings=make_readings(hold_seconds=45))
    )
    assert result.outcome is Outcome.PASS
