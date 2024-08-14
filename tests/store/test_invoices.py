from datetime import date

import pytest

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.invoice import Invoice, InvoiceLine
from starstamp.model.money import Money
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.invoices import InvoiceRepository
from starstamp.store.owners import OwnerRepository

from ..support.factories import make_cylinder

KEY = CylinderKey("NCI", "A4471")


@pytest.fixture
def invoices(
    book: Book, owners: OwnerRepository, cylinders: CylinderRepository
) -> InvoiceRepository:
    cylinders.add(make_cylinder(key=KEY), owners.id_of("WELD1"), date(2024, 1, 2))
    return InvoiceRepository(book.connection)


def an_invoice(number: str = "I2024-0001", **changes: object) -> Invoice:
    base: dict[str, object] = {
        "number": number,
        "owner_code": "WELD1",
        "raised_on": date(2024, 7, 1),
        "due_on": date(2024, 7, 31),
        "first_day": date(2024, 6, 1),
        "last_day": date(2024, 6, 30),
        "lines": (
            InvoiceLine(
                code="REQUAL_WJ",
                description="water jacket requalification",
                performed_on=date(2024, 6, 12),
                unit=Money.parse("14.50"),
                cylinder_key="NCI/A4471",
            ),
            InvoiceLine(
                code="HANDLING",
                description="lot handling",
                performed_on=date(2024, 6, 3),
                unit=Money.parse("5.00"),
            ),
        ),
    }
    base.update(changes)
    return Invoice(**base)  # type: ignore[arg-type]


def test_an_invoice_round_trips(
    invoices: InvoiceRepository, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    written = invoices.add(an_invoice(), owners.id_of("WELD1"), {"NCI/A4471": cylinders.id_of(KEY)})
    assert written.total == Money.parse("19.50")
    read_back = invoices.by_number("i2024-0001")
    assert len(read_back.lines) == 2
    assert read_back.lines[0].cylinder_key == "NCI/A4471"
    assert read_back.lines[1].cylinder_key is None


def test_numbers_run_on(invoices: InvoiceRepository, owners: OwnerRepository) -> None:
    assert invoices.next_number(2024) == "I2024-0001"
    invoices.add(an_invoice(), owners.id_of("WELD1"), {})
    assert invoices.next_number(2024) == "I2024-0002"
    assert invoices.next_number(2025) == "I2025-0001"


def test_a_duplicate_number(invoices: InvoiceRepository, owners: OwnerRepository) -> None:
    invoices.add(an_invoice(), owners.id_of("WELD1"), {})
    with pytest.raises(ConflictError, match="already raised"):
        invoices.add(an_invoice(), owners.id_of("WELD1"), {})


def test_a_missing_invoice(invoices: InvoiceRepository) -> None:
    with pytest.raises(NotFoundError, match="no invoice I2024-9999"):
        invoices.by_number("I2024-9999")


def test_settling(invoices: InvoiceRepository, owners: OwnerRepository) -> None:
    invoices.add(an_invoice(), owners.id_of("WELD1"), {})
    settled = invoices.settle("I2024-0001", date(2024, 7, 20))
    assert settled.settled_on == date(2024, 7, 20)
    with pytest.raises(ConflictError, match="was settled on"):
        invoices.settle("I2024-0001", date(2024, 7, 21))


def test_settling_before_it_was_raised(
    invoices: InvoiceRepository, owners: OwnerRepository
) -> None:
    invoices.add(an_invoice(), owners.id_of("WELD1"), {})
    with pytest.raises(ConflictError, match="was raised on"):
        invoices.settle("I2024-0001", date(2024, 6, 1))


def test_outstanding_and_overdue(invoices: InvoiceRepository, owners: OwnerRepository) -> None:
    invoices.add(an_invoice(), owners.id_of("WELD1"), {})
    invoices.add(
        an_invoice("I2024-0002", raised_on=date(2024, 8, 1), due_on=date(2024, 8, 31)),
        owners.id_of("WELD1"),
        {},
    )
    assert [item.number for item in invoices.outstanding()] == ["I2024-0001", "I2024-0002"]
    assert [item.number for item in invoices.overdue(date(2024, 8, 15))] == ["I2024-0001"]
    invoices.settle("I2024-0001", date(2024, 8, 2))
    assert invoices.overdue(date(2024, 8, 15)) == []


def test_for_owner(invoices: InvoiceRepository, owners: OwnerRepository) -> None:
    invoices.add(an_invoice(), owners.id_of("WELD1"), {})
    assert [item.number for item in invoices.for_owner("weld1")] == ["I2024-0001"]


def test_which_records_have_been_billed(
    invoices: InvoiceRepository, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    assert invoices.billed_event_ids("WELD1") == set()
    lines = (
        InvoiceLine(
            code="REQUAL_WJ",
            description="wj",
            performed_on=date(2024, 6, 12),
            unit=Money.parse("14.50"),
            cylinder_key="NCI/A4471",
            event_id=None,
        ),
    )
    invoices.add(an_invoice(lines=lines), owners.id_of("WELD1"), {})
    assert invoices.billed_event_ids("WELD1") == set()
