from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind
from starstamp.model.money import Money
from starstamp.model.pricing import PriceItem
from starstamp.reporting import unbilled
from starstamp.service.billing import BillingService
from starstamp.store.db import Book
from starstamp.store.pricing import PriceRepository

from ..support.factories import make_cylinder, make_observation
from ..support.requests import requalify
from ..support.shop import stock

TODAY = date(2024, 7, 1)


def priced(book: Book) -> None:
    for code, amount in (("REQUAL_WJ", "14.50"), ("CONDEMN", "9.00")):
        PriceRepository(book.connection).add(
            PriceItem(
                code=code,
                description=code.lower(),
                amount=Money.parse(amount),
                effective_from=date(2023, 1, 1),
            )
        )


def test_a_book_with_nothing_done(shop_book: Book) -> None:
    found = unbilled.build(shop_book, TODAY)
    assert found.events == ()
    assert found.value == Money.zero()
    assert "has been billed" in found.describe()
    assert unbilled.render(found) == found.describe()


def test_work_that_has_not_been_invoiced(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book)
    found = unbilled.build(shop_book, TODAY)
    assert len(found.events) == 1
    assert found.value == Money.parse("14.50")
    assert "the oldest is 19 days old" in found.describe()


def test_invoiced_work_drops_out(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book)
    BillingService(shop_book).raise_invoice("WELD1", date(2024, 6, 1), date(2024, 6, 30), TODAY)
    assert unbilled.build(shop_book, TODAY).events == ()


def test_a_suspended_record_is_not_unbilled(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book, observations=(make_observation(DefectKind.THREAD_DAMAGE),))
    assert unbilled.build(shop_book, TODAY).events == ()


def test_a_condemnation_counts(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    found = unbilled.build(shop_book, TODAY)
    assert len(found.events) == 1
    assert found.value == Money.parse("14.50")


def test_grouping_by_account(shop_book: Book) -> None:
    priced(shop_book)
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    requalify(shop_book)
    requalify(shop_book, key=other)
    found = unbilled.build(shop_book, TODAY)
    assert found.by_owner() == {"WELD1": Money.parse("29.00")}


def test_work_with_no_price_yet_is_still_listed(shop_book: Book) -> None:
    requalify(shop_book)
    found = unbilled.build(shop_book, TODAY)
    assert len(found.events) == 1
    assert found.value == Money.zero()


def test_rendering(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book)
    text = unbilled.render(unbilled.build(shop_book, TODAY))
    assert "NCI/A4471" in text
    assert "WELD1" in text
    assert "14.50" in text
