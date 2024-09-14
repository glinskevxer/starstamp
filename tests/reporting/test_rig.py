from datetime import date
from fractions import Fraction

from starstamp.model.calibration import InstrumentKind
from starstamp.model.cylinder import CylinderKey
from starstamp.model.method import Method
from starstamp.model.units import Expansion
from starstamp.reporting import rig
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.db import Book

from ..support.factories import make_certificate, make_check, make_readings
from ..support.shop import DAY, SYSTEM

KEY = CylinderKey("NCI", "A4471")
FIRST = date(2024, 6, 1)
LAST = date(2024, 6, 30)


def requalify(book: Book, **changes: object) -> None:
    base: dict[str, object] = {
        "key": KEY,
        "day": DAY,
        "technician_badge": "JT7",
        "method": Method.VOLUMETRIC,
        "system_code": SYSTEM,
        "readings": make_readings(),
    }
    base.update(changes)
    RequalificationService(book).perform(RequalificationRequest(**base))  # type: ignore[arg-type]


def test_a_quiet_rig(shop_book: Book) -> None:
    standing = rig.build(shop_book, SYSTEM, FIRST, LAST)
    assert standing.tested == 0
    assert standing.checks_run == 1
    assert len(standing.certificates) == 4


def test_work_is_counted(shop_book: Book) -> None:
    requalify(shop_book)
    standing = rig.build(shop_book, SYSTEM, FIRST, LAST)
    assert standing.tested == 1
    assert standing.condemned == 0


def test_a_condemnation_is_counted_separately(shop_book: Book) -> None:
    requalify(
        shop_book,
        readings=make_readings(
            total_expansion=Expansion.parse("100.0"), permanent_expansion=Expansion.parse("11.0")
        ),
    )
    standing = rig.build(shop_book, SYSTEM, FIRST, LAST)
    assert standing.condemned == 1


def test_drift_is_the_average_signed_deviation(shop_book: Book) -> None:
    calibration = CalibrationRepository(shop_book.connection)
    calibration.record_check(make_check(day=date(2024, 6, 13), observed=Expansion(404)))
    calibration.record_check(make_check(day=date(2024, 6, 14), observed=Expansion(406)))
    standing = rig.build(shop_book, SYSTEM, FIRST, LAST)
    assert standing.checks_run == 3
    assert standing.drift() == Fraction(11, 12)
    assert len(standing.failed_checks) == 1


def test_a_check_out_of_tolerance_is_named(shop_book: Book) -> None:
    CalibrationRepository(shop_book.connection).record_check(
        make_check(day=date(2024, 6, 13), observed=Expansion(380))
    )
    standing = rig.build(shop_book, SYSTEM, FIRST, LAST)
    assert len(standing.failed_checks) == 1
    assert "out of tolerance" in standing.describe(DAY)


def test_certificates_about_to_expire(shop_book: Book) -> None:
    standing = rig.build(shop_book, SYSTEM, FIRST, LAST)
    assert standing.expiring_within(date(2028, 12, 1), 90)
    assert not standing.expiring_within(DAY, 90)
    assert standing.expired_on(date(2030, 1, 1))
    assert "EXPIRED" in standing.describe(date(2030, 1, 1))
    assert "due:" in standing.describe(date(2028, 12, 1))


def test_every_rig_at_once(shop_book: Book) -> None:
    CalibrationRepository(shop_book.connection).add_certificate(
        make_certificate(InstrumentKind.PRESSURE_INDICATOR, system_code="WJ-2", serial="PG-9")
    )
    standings = rig.build_all(shop_book, FIRST, LAST)
    assert [standing.system_code for standing in standings] == ["WJ-1", "WJ-2"]


def test_rendering(shop_book: Book) -> None:
    requalify(shop_book)
    text = rig.render(rig.build_all(shop_book, FIRST, LAST), DAY)
    assert "WJ-1" in text
    assert "drift" in text
    assert rig.render([], DAY) == "no test systems on file"


def test_a_rig_with_no_checks_has_no_drift(shop_book: Book) -> None:
    standing = rig.build(shop_book, SYSTEM, date(2023, 1, 1), date(2023, 12, 31))
    assert standing.drift() == 0
