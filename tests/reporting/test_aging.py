from datetime import date

from starstamp.model.invoice import Invoice, InvoiceLine
from starstamp.model.money import Money
from starstamp.reporting import aging
from starstamp.store.db import Book
from starstamp.store.invoices import InvoiceRepository
from starstamp.store.owners import OwnerRepository

TODAY = date(2024, 10, 1)


def an_invoice(number: str, due: date, amount: str = "100.00") -> Invoice:
    return Invoice(
        number=number,
        owner_code="WELD1",
        raised_on=due - (due - due),
        due_on=due,
        first_day=date(2024, 1, 1),
        last_day=date(2024, 1, 31),
        lines=(
            InvoiceLine(
                code="REQUAL_WJ",
                description="wj",
                performed_on=date(2024, 1, 15),
                unit=Money.parse(amount),
            ),
        ),
    )


def test_the_buckets_are_measured_from_the_due_date() -> None:
    assert aging.bucket_for(0) == "current"
    assert aging.bucket_for(-5) == "current"
    assert aging.bucket_for(1) == "1 to 30"
    assert aging.bucket_for(30) == "1 to 30"
    assert aging.bucket_for(31) == "31 to 60"
    assert aging.bucket_for(61) == "61 to 90"
    assert aging.bucket_for(91) == "over 90"


def test_an_account_with_nothing_outstanding(shop_book: Book) -> None:
    built = aging.build(shop_book, TODAY)
    assert built.accounts == ()
    assert built.outstanding == Money.zero()
    assert built.worst() is None
    assert "nothing outstanding" in aging.render(built)


def test_one_account_across_buckets(shop_book: Book) -> None:
    invoices = InvoiceRepository(shop_book.connection)
    owner_id = OwnerRepository(shop_book.connection).id_of("WELD1")
    invoices.add(an_invoice("I2024-0001", date(2024, 9, 20)), owner_id, {})
    invoices.add(an_invoice("I2024-0002", date(2024, 6, 1), "50.00"), owner_id, {})
    invoices.add(an_invoice("I2024-0003", date(2024, 10, 30), "25.00"), owner_id, {})
    built = aging.build(shop_book, TODAY)
    account = built.accounts[0]
    buckets = account.buckets()
    assert buckets["current"] == Money.parse("25.00")
    assert buckets["1 to 30"] == Money.parse("100.00")
    assert buckets["over 90"] == Money.parse("50.00")
    assert account.outstanding == Money.parse("175.00")
    assert account.oldest_days == 122


def test_a_settled_invoice_drops_out(shop_book: Book) -> None:
    invoices = InvoiceRepository(shop_book.connection)
    owner_id = OwnerRepository(shop_book.connection).id_of("WELD1")
    invoices.add(an_invoice("I2024-0001", date(2024, 9, 20)), owner_id, {})
    invoices.settle("I2024-0001", date(2024, 9, 25))
    assert aging.build(shop_book, TODAY).accounts == ()


def test_the_whole_book_totals(shop_book: Book) -> None:
    invoices = InvoiceRepository(shop_book.connection)
    owner_id = OwnerRepository(shop_book.connection).id_of("WELD1")
    invoices.add(an_invoice("I2024-0001", date(2024, 9, 20)), owner_id, {})
    built = aging.build(shop_book, TODAY)
    assert built.outstanding == Money.parse("100.00")
    assert built.buckets()["1 to 30"] == Money.parse("100.00")
    worst = built.worst()
    assert worst is not None
    assert worst.owner_code == "WELD1"
    assert "$100.00 outstanding across 1 accounts" in built.describe()


def test_rendering(shop_book: Book) -> None:
    invoices = InvoiceRepository(shop_book.connection)
    owner_id = OwnerRepository(shop_book.connection).id_of("WELD1")
    invoices.add(an_invoice("I2024-0001", date(2024, 6, 1)), owner_id, {})
    text = aging.render(aging.build(shop_book, TODAY))
    assert "WELD1" in text
    assert "over 90" in text
    assert "122" in text
