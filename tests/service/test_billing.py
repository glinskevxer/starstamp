from datetime import date

import pytest

from starstamp.errors import ConflictError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind
from starstamp.model.method import Method
from starstamp.model.money import Money
from starstamp.model.pricing import PriceItem
from starstamp.service.billing import BillingService
from starstamp.service.receiving import ReceivingService
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.db import Book
from starstamp.store.pricing import PriceRepository

from ..support.factories import make_observation, make_readings
from ..support.shop import DAY, SYSTEM

KEY = CylinderKey("NCI", "A4471")
FIRST = date(2024, 6, 1)
LAST = date(2024, 6, 30)
RAISED = date(2024, 7, 1)


@pytest.fixture
def priced(shop_book: Book) -> Book:
    prices = PriceRepository(shop_book.connection)
    for code, description, amount in (
        ("REQUAL_WJ", "water jacket requalification", "14.50"),
        ("REQUAL_VISUAL", "external visual requalification", "6.00"),
        ("CONDEMN", "condemnation and disposal", "9.00"),
        ("HANDLING", "lot handling", "5.00"),
    ):
        prices.add(
            PriceItem(
                code=code,
                description=description,
                amount=Money.parse(amount),
                effective_from=date(2023, 1, 1),
            )
        )
    return shop_book


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


def test_a_pass_is_one_line(priced: Book) -> None:
    requalify(priced)
    draft = BillingService(priced).draft("WELD1", FIRST, LAST, RAISED)
    assert draft.total == Money.parse("14.50")
    assert draft.invoice.lines[0].event_id is not None


def test_a_condemnation_carries_a_disposal_line(priced: Book) -> None:
    requalify(priced, observations=(make_observation(DefectKind.BULGE),))
    draft = BillingService(priced).draft("WELD1", FIRST, LAST, RAISED)
    assert draft.total == Money.parse("23.50")
    assert sorted(draft.invoice.by_code()) == ["CONDEMN", "REQUAL_WJ"]


def test_a_suspended_cylinder_is_not_billed(priced: Book) -> None:
    requalify(priced, observations=(make_observation(DefectKind.THREAD_DAMAGE),))
    draft = BillingService(priced).draft("WELD1", FIRST, LAST, RAISED)
    assert draft.is_empty
    assert "suspended" in draft.skipped[0]


def test_a_lot_received_in_the_window_carries_handling(priced: Book) -> None:
    ReceivingService(priced).receive("WELD1", date(2024, 6, 3), [KEY])
    requalify(priced)
    draft = BillingService(priced).draft("WELD1", FIRST, LAST, RAISED)
    assert draft.total == Money.parse("19.50")


def test_the_price_that_was_in_force_that_day_is_used(priced: Book) -> None:
    PriceRepository(priced.connection).raise_price(
        "REQUAL_WJ", Money.parse("16.00"), date(2024, 7, 1), "water jacket requalification"
    )
    requalify(priced)
    draft = BillingService(priced).draft("WELD1", FIRST, LAST, RAISED)
    assert draft.total == Money.parse("14.50")


def test_raising_an_invoice_writes_it(priced: Book) -> None:
    requalify(priced)
    service = BillingService(priced)
    invoice = service.raise_invoice("WELD1", FIRST, LAST, RAISED)
    assert invoice.number == "I2024-0001"
    assert service.invoices.by_number("I2024-0001").total == Money.parse("14.50")


def test_the_same_work_is_not_billed_twice(priced: Book) -> None:
    requalify(priced)
    service = BillingService(priced)
    service.raise_invoice("WELD1", FIRST, LAST, RAISED)
    second = service.draft("WELD1", FIRST, LAST, date(2024, 8, 1))
    assert second.is_empty
    assert "already billed" in second.skipped[0]


def test_an_empty_invoice_is_refused(priced: Book) -> None:
    with pytest.raises(ConflictError, match="nothing to bill WELD1"):
        BillingService(priced).raise_invoice("WELD1", FIRST, LAST, RAISED)


def test_a_backwards_window(priced: Book) -> None:
    with pytest.raises(ConflictError, match="ends after it starts"):
        BillingService(priced).draft("WELD1", LAST, FIRST, RAISED)


def test_the_due_date_comes_off_the_account_terms(priced: Book) -> None:
    requalify(priced)
    invoice = BillingService(priced).raise_invoice("WELD1", FIRST, LAST, RAISED)
    assert invoice.due_on == date(2024, 7, 31)


def test_a_reversed_record_is_not_billed(priced: Book) -> None:
    requalify(priced)
    service = BillingService(priced)
    service.events.reverse(1, "rig out of calibration")
    draft = service.draft("WELD1", FIRST, LAST, RAISED)
    assert draft.is_empty
    assert "reversed" in draft.skipped[0]
