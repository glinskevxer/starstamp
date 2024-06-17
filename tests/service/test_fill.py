from datetime import date

from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.model.method import Method
from starstamp.model.service import ARGON, NITROGEN
from starstamp.service.fill import FillService
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book

from ..support.factories import make_cylinder, make_readings
from ..support.shop import DAY, SYSTEM, stock

KEY = CylinderKey("NCI", "A4471")


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


def test_a_freshly_tested_cylinder_may_be_filled(shop_book: Book) -> None:
    requalify(shop_book)
    decision = FillService(shop_book).decision(KEY, NITROGEN, date(2024, 7, 1))
    assert decision.allowed
    assert decision.due is not None
    assert decision.due.year == 2034


def test_the_star_recorded_at_the_bench_is_the_one_used(shop_book: Book) -> None:
    requalify(shop_book)
    service = FillService(shop_book)
    late = service.decision(KEY, NITROGEN, date(2032, 7, 1))
    assert late.allowed


def test_a_cylinder_that_never_earned_a_star_falls_due_in_five(shop_book: Book) -> None:
    unmarked = stock(
        shop_book,
        make_cylinder(
            key=CylinderKey("PST", "C900"),
            rejection_elastic_expansion=None,
            nominal_wall_thousandths_in=220,
            wall_source="data sheet",
        ),
    )
    requalify(shop_book, key=unmarked)
    service = FillService(shop_book)
    assert service.decision(unmarked, NITROGEN, date(2029, 5, 1)).allowed
    later = service.decision(unmarked, NITROGEN, date(2032, 7, 1))
    assert not later.allowed
    assert not later.terminal
    assert "out of test since 2029-06" in later.describe()


def test_an_untested_cylinder_cannot_be_filled(shop_book: Book) -> None:
    decision = FillService(shop_book).decision(KEY, NITROGEN, DAY)
    assert "no standing requalification" in decision.refusals


def test_the_due_list_puts_the_soonest_first(shop_book: Book) -> None:
    requalify(shop_book)
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12"), service=ARGON))
    rows = FillService(shop_book).due_within(date(2034, 4, 1), 3)
    assert [str(row.cylinder.key) for row in rows] == ["NCI/A4471", str(other)]
    assert rows[0].months_left == 2
    assert rows[1].never_tested


def test_the_due_list_can_be_narrowed_to_an_account(shop_book: Book) -> None:
    requalify(shop_book)
    rows = FillService(shop_book).due_within(date(2034, 4, 1), 3, owner_code="WELD1")
    assert len(rows) == 1


def test_nothing_due_yet(shop_book: Book) -> None:
    requalify(shop_book)
    rows = FillService(shop_book).due_within(date(2025, 1, 1), 3, owner_code="WELD1")
    assert rows == []


def test_an_overdue_row_reads_as_overdue(shop_book: Book) -> None:
    requalify(shop_book)
    rows = FillService(shop_book).due_within(date(2035, 1, 1), 3, owner_code="WELD1")
    assert rows[0].overdue


def test_a_condemned_cylinder_drops_off_the_due_list(shop_book: Book) -> None:
    requalify(shop_book)
    CylinderRepository(shop_book.connection).set_status(KEY, CylinderStatus.CONDEMNED)
    rows = FillService(shop_book).due_within(date(2034, 4, 1), 3)
    assert [str(row.cylinder.key) for row in rows] == []
