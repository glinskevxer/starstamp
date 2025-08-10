from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind
from starstamp.model.money import Money
from starstamp.model.pricing import PriceItem
from starstamp.reporting import account
from starstamp.service.billing import BillingService
from starstamp.service.receiving import ReceivingService
from starstamp.store.db import Book
from starstamp.store.pricing import PriceRepository

from ..support.factories import make_observation
from ..support.requests import requalify

KEY = CylinderKey("NCI", "A4471")
FIRST = date(2024, 6, 1)
LAST = date(2024, 6, 30)
TODAY = date(2024, 7, 1)


def test_a_quiet_account(shop_book: Book) -> None:
    page = account.build(shop_book, "WELD1", FIRST, LAST, TODAY)
    assert page.standing.size == 1
    assert page.owed == Money.zero()
    assert page.in_the_shop == ()
    assert "1 cylinders, 0 here" in page.describe()


def test_an_account_with_work_and_money(shop_book: Book) -> None:
    PriceRepository(shop_book.connection).add(
        PriceItem(
            code="REQUAL_WJ",
            description="wj",
            amount=Money.parse("14.50"),
            effective_from=date(2023, 1, 1),
        )
    )
    requalify(shop_book)
    BillingService(shop_book).raise_invoice("WELD1", FIRST, LAST, date(2024, 6, 30))
    page = account.build(shop_book, "WELD1", FIRST, LAST, TODAY)
    assert page.owed == Money.parse("14.50")
    assert page.oldest_bucket == "current"


def test_cylinders_in_the_shop_show(shop_book: Book) -> None:
    ReceivingService(shop_book).receive("WELD1", date(2024, 6, 3), [KEY])
    page = account.build(shop_book, "WELD1", FIRST, LAST, TODAY)
    assert len(page.in_the_shop) == 1
    assert page.open_lots == ("L2024-0001",)


def test_letters_waiting_are_counted(shop_book: Book) -> None:
    from starstamp.service.notices import NoticeService

    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    NoticeService(shop_book).draft_condemnations(date(2024, 6, 13))
    page = account.build(shop_book, "WELD1", FIRST, LAST, TODAY)
    assert page.unsent_letters == 1


def test_an_overdue_invoice_ages(shop_book: Book) -> None:
    PriceRepository(shop_book.connection).add(
        PriceItem(
            code="REQUAL_WJ",
            description="wj",
            amount=Money.parse("14.50"),
            effective_from=date(2023, 1, 1),
        )
    )
    requalify(shop_book)
    BillingService(shop_book).raise_invoice("WELD1", FIRST, LAST, date(2024, 6, 30))
    page = account.build(shop_book, "WELD1", FIRST, LAST, date(2024, 9, 15))
    assert page.oldest_bucket == "31 to 60"


def test_rendering(shop_book: Book) -> None:
    requalify(shop_book)
    text = account.render(account.build(shop_book, "WELD1", FIRST, LAST, TODAY))
    assert "WELD1 Cascade Welding Supply" in text
    assert "terms" in text
