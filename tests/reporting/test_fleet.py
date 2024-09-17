from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind
from starstamp.model.method import Method
from starstamp.model.service import ARGON
from starstamp.reporting import fleet
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.db import Book

from ..support.factories import make_cylinder, make_observation, make_readings
from ..support.shop import DAY, SYSTEM, stock

KEY = CylinderKey("NCI", "A4471")


def requalify(book: Book, key: CylinderKey = KEY, **changes: object) -> None:
    base: dict[str, object] = {
        "key": key,
        "day": DAY,
        "technician_badge": "JT7",
        "method": Method.VOLUMETRIC,
        "system_code": SYSTEM,
        "readings": make_readings(),
    }
    base.update(changes)
    RequalificationService(book).perform(RequalificationRequest(**base))  # type: ignore[arg-type]


def test_an_untested_fleet(shop_book: Book) -> None:
    standing = fleet.build(shop_book, "WELD1", DAY)
    assert standing.size == 1
    assert len(standing.never_tested()) == 1
    assert standing.condemn_rate() == 0
    assert "1 never requalified here" in standing.describe()


def test_counts_by_status_and_service(shop_book: Book) -> None:
    stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12"), service=ARGON))
    standing = fleet.build(shop_book, "weld1", DAY)
    assert standing.by_status() == {"in_service": 2}
    assert standing.by_service() == {"AR": 1, "N2": 1}


def test_a_tested_cylinder_falls_out_of_the_untested_list(shop_book: Book) -> None:
    requalify(shop_book)
    standing = fleet.build(shop_book, "WELD1", DAY)
    assert standing.never_tested() == ()
    assert standing.due_by_month() == {"2034-06": 1}


def test_overdue_cylinders_are_flagged(shop_book: Book) -> None:
    requalify(shop_book)
    standing = fleet.build(shop_book, "WELD1", date(2035, 1, 1))
    assert len(standing.overdue()) == 1
    assert "1 out of test" in standing.describe()


def test_due_within_a_window(shop_book: Book) -> None:
    requalify(shop_book)
    standing = fleet.build(shop_book, "WELD1", date(2034, 4, 1))
    assert len(standing.due_within(6)) == 1
    assert len(standing.due_within(1)) == 0


def test_condemnations_are_counted_and_rated(shop_book: Book) -> None:
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    requalify(shop_book, other, observations=(make_observation(DefectKind.BULGE),))
    standing = fleet.build(shop_book, "WELD1", DAY)
    assert standing.condemned_ever == 1
    assert standing.condemned_this_year == 1
    assert float(standing.condemn_rate()) > 0
    assert "1 condemned this year" in standing.describe()


def test_condemnations_from_an_earlier_year(shop_book: Book) -> None:
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    requalify(shop_book, other, observations=(make_observation(DefectKind.BULGE),))
    standing = fleet.build(shop_book, "WELD1", date(2025, 3, 1))
    assert standing.condemned_ever == 1
    assert standing.condemned_this_year == 0


def test_rendering(shop_book: Book) -> None:
    requalify(shop_book)
    text = fleet.render(fleet.build(shop_book, "WELD1", date(2034, 4, 1)))
    assert "WELD1 holds 1 cylinders" in text
    assert "due month" in text
    assert "NCI/A4471" in text


def test_rendering_a_quiet_fleet(shop_book: Book) -> None:
    text = fleet.render(fleet.build(shop_book, "WELD1", DAY))
    assert "never requalified here" in text
    assert "due month" not in text


def test_what_is_on_the_floor(shop_book: Book) -> None:
    assert fleet.in_shop(shop_book, "WELD1") == []
    requalify(shop_book, observations=(make_observation(DefectKind.THREAD_DAMAGE),))
    assert [cylinder.key for cylinder in fleet.in_shop(shop_book, "WELD1")] == [KEY]
