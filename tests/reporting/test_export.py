import csv
import io
from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.method import Method
from starstamp.model.money import Money
from starstamp.model.pricing import PriceItem
from starstamp.reporting import export
from starstamp.service.billing import BillingService
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.db import Book
from starstamp.store.pricing import PriceRepository

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


def parse(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def test_the_cylinder_export(shop_book: Book) -> None:
    stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    rows = parse(export.cylinders_csv(shop_book))
    assert len(rows) == 2
    assert rows[0]["cylinder"] == "NCI/A4471"
    assert rows[0]["specification"] == "DOT-3AA2015"
    assert rows[0]["wall_in"] == "0.220"
    assert rows[0]["ree_cc"] == "125.0"


def test_the_cylinder_export_for_one_account(shop_book: Book) -> None:
    rows = parse(export.cylinders_csv(shop_book, "weld1"))
    assert len(rows) == 1


def test_a_cylinder_with_nothing_measured(shop_book: Book) -> None:
    stock(
        shop_book,
        make_cylinder(key=CylinderKey("PST", "B12"), rejection_elastic_expansion=None),
    )
    rows = {row["cylinder"]: row for row in parse(export.cylinders_csv(shop_book))}
    assert rows["PST/B12"]["ree_cc"] == ""
    assert rows["PST/B12"]["wall_in"] == ""


def test_the_event_export(shop_book: Book) -> None:
    requalify(shop_book)
    rows = parse(export.events_csv(shop_book, date(2024, 1, 1), date(2024, 12, 31)))
    assert len(rows) == 1
    assert rows[0]["method"] == "volumetric"
    assert rows[0]["total_cc"] == "110.0"
    assert rows[0]["starred"] == "yes"
    assert rows[0]["state"] == "recorded"


def test_the_event_export_of_a_quiet_window(shop_book: Book) -> None:
    text = export.events_csv(shop_book, date(2023, 1, 1), date(2023, 12, 31))
    assert text.strip() == ",".join(export.EVENT_HEADERS)


def test_the_invoice_export(shop_book: Book) -> None:
    PriceRepository(shop_book.connection).add(
        PriceItem(
            code="REQUAL_WJ",
            description="water jacket requalification",
            amount=Money.parse("14.50"),
            effective_from=date(2023, 1, 1),
        )
    )
    requalify(shop_book)
    BillingService(shop_book).raise_invoice(
        "WELD1", date(2024, 6, 1), date(2024, 6, 30), date(2024, 7, 1)
    )
    rows = parse(export.invoices_csv(shop_book, "WELD1"))
    assert rows[0]["invoice"] == "I2024-0001"
    assert rows[0]["amount"] == "14.50"
    assert rows[0]["settled_on"] == ""


def test_commas_inside_a_field_survive(shop_book: Book) -> None:
    from starstamp.model.defect import DefectKind

    from ..support.factories import make_observation

    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    rows = parse(export.events_csv(shop_book, date(2024, 1, 1), date(2024, 12, 31)))
    assert rows[0]["reasons"] == "bulge"
    assert rows[0]["outcome"] == "condemn"


def test_the_writer_quotes_what_it_must() -> None:
    text = export.to_csv(("a", "b"), [["one, two", 'say "hello"']])
    assert '"one, two"' in text
    assert text.endswith("\n")
    assert parse(text)[0]["b"] == 'say "hello"'
