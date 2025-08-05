from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind
from starstamp.service.notices import NoticeService
from starstamp.service.receiving import ReceivingService
from starstamp.service.worklist import WorklistService
from starstamp.store.db import Book

from ..support.factories import make_observation
from ..support.requests import requalify
from ..support.shop import DAY

KEY = CylinderKey("NCI", "A4471")


def test_a_shop_with_nothing_outstanding(shop_book: Book) -> None:
    built = WorklistService(shop_book).build(DAY)
    assert built.is_clear
    assert "nothing outstanding" in built.describe()


def test_a_held_cylinder_is_on_the_list(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.THREAD_DAMAGE),))
    built = WorklistService(shop_book).build(DAY)
    assert built.of_kind("held for repair")
    assert "NCI/A4471" in built.of_kind("held for repair")[0].detail


def test_a_late_letter_comes_first(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    NoticeService(shop_book).draft_condemnations(date(2024, 6, 13))
    built = WorklistService(shop_book).build(date(2024, 7, 20))
    assert built.items[0].kind in {"letter overdue", "not rendered"}
    assert built.items[0].urgency == 0


def test_a_cylinder_nobody_rendered(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    NoticeService(shop_book).draft_condemnations(date(2024, 6, 13))
    built = WorklistService(shop_book).build(date(2024, 7, 20))
    assert built.of_kind("not rendered")


def test_work_that_was_never_billed(shop_book: Book) -> None:
    requalify(shop_book)
    built = WorklistService(shop_book).build(DAY)
    assert built.of_kind("unbilled")
    assert "1 records" in built.of_kind("unbilled")[0].detail


def test_a_certificate_about_to_expire(shop_book: Book) -> None:
    built = WorklistService(shop_book).build(date(2028, 12, 15))
    assert built.of_kind("certificate due")


def test_an_expired_certificate_and_a_lapsed_number(shop_book: Book) -> None:
    built = WorklistService(shop_book).build(date(2030, 1, 1))
    assert built.of_kind("certificate expired")
    assert built.of_kind("rin lapsed")
    assert built.items[0].urgency == 0


def test_a_lot_nobody_collected(shop_book: Book) -> None:
    receiving = ReceivingService(shop_book)
    receiving.receive("WELD1", date(2024, 6, 3), [KEY])
    requalify(shop_book)
    receiving.ready("L2024-0001")
    built = WorklistService(shop_book).build(date(2025, 1, 1))
    assert built.of_kind("uncollected")


def test_cylinders_coming_due(shop_book: Book) -> None:
    requalify(shop_book)
    built = WorklistService(shop_book).build(date(2034, 4, 1), due_within=3)
    assert built.of_kind("coming due")
    assert "due 06-34" in built.of_kind("coming due")[0].detail


def test_the_kinds_are_listed(shop_book: Book) -> None:
    requalify(shop_book)
    built = WorklistService(shop_book).build(DAY)
    assert "unbilled" in built.kinds()


def test_an_overdue_invoice_is_on_the_list(shop_book: Book) -> None:
    from starstamp.model.money import Money
    from starstamp.model.pricing import PriceItem
    from starstamp.service.billing import BillingService
    from starstamp.store.pricing import PriceRepository

    PriceRepository(shop_book.connection).add(
        PriceItem(
            code="REQUAL_WJ",
            description="wj",
            amount=Money.parse("14.50"),
            effective_from=date(2023, 1, 1),
        )
    )
    requalify(shop_book)
    BillingService(shop_book).raise_invoice(
        "WELD1", date(2024, 6, 1), date(2024, 6, 30), date(2024, 7, 1)
    )
    built = WorklistService(shop_book).build(date(2024, 9, 1))
    assert built.of_kind("invoice overdue")
    assert "I2024-0001" in built.of_kind("invoice overdue")[0].detail


def test_a_lapsed_sign_off_is_on_the_list(shop_book: Book) -> None:
    from starstamp.store.facility import TechnicianRepository

    TechnicianRepository(shop_book.connection).renew("JT7", date(2024, 1, 1))
    built = WorklistService(shop_book).build(DAY)
    assert built.of_kind("sign off lapsed")


def test_a_sign_off_about_to_lapse(shop_book: Book) -> None:
    from starstamp.store.facility import TechnicianRepository

    TechnicianRepository(shop_book.connection).renew("JT7", date(2024, 7, 1))
    built = WorklistService(shop_book).build(DAY)
    assert built.of_kind("sign off due")


def test_a_rin_about_to_lapse(shop_book: Book) -> None:
    built = WorklistService(shop_book).build(date(2026, 4, 1))
    assert built.of_kind("rin due")
