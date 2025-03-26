from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import DefectKind
from starstamp.model.method import Method
from starstamp.model.money import Money
from starstamp.model.pricing import PriceItem
from starstamp.reporting import close
from starstamp.service.billing import BillingService
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.db import Book
from starstamp.store.pricing import PriceRepository

from ..support.factories import make_cylinder, make_observation, make_readings
from ..support.shop import DAY, SYSTEM, stock

KEY = CylinderKey("NCI", "A4471")
JUNE = StampedMonth(2024, 6)


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


def test_a_quiet_month(shop_book: Book) -> None:
    built = close.build(shop_book, JUNE, date(2024, 7, 1))
    assert built.worked == 0
    assert built.invoiced == Money.zero()
    assert built.earned_per_cylinder == Money.zero()
    assert "2024-06: 0 cylinders" in built.describe()


def test_a_month_with_work_and_an_invoice(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book)
    BillingService(shop_book).raise_invoice(
        "WELD1", JUNE.first_day(), JUNE.last_day(), date(2024, 6, 30)
    )
    built = close.build(shop_book, JUNE, date(2024, 7, 1))
    assert built.worked == 1
    assert built.invoiced == Money.parse("14.50")
    assert built.outstanding == Money.parse("14.50")
    assert built.settled == Money.zero()
    assert built.earned_per_cylinder == Money.parse("14.50")


def test_a_settled_invoice_shows_as_settled(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book)
    service = BillingService(shop_book)
    service.raise_invoice("WELD1", JUNE.first_day(), JUNE.last_day(), date(2024, 6, 30))
    service.invoices.settle("I2024-0001", date(2024, 6, 30))
    built = close.build(shop_book, JUNE, date(2024, 7, 1))
    assert built.settled == Money.parse("14.50")
    assert built.outstanding == Money.zero()


def test_condemnations_come_through(shop_book: Book) -> None:
    priced(shop_book)
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    requalify(shop_book, other, observations=(make_observation(DefectKind.BULGE),))
    built = close.build(shop_book, JUNE, date(2024, 7, 1))
    assert built.tally.condemned == 1
    assert built.condemned.count == 1
    assert "1 condemned between" in close.render(built)


def test_the_forecast_is_part_of_the_pack(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book)
    built = close.build(shop_book, JUNE, date(2034, 1, 1))
    assert built.ahead.cylinders == 1
    assert "cylinders due over" in close.render(built)


def test_rendering(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book)
    text = close.render(close.build(shop_book, JUNE, date(2024, 7, 1)))
    assert "month             2024-06" in text
    assert "condemn rate      0.0%" in text
    assert "per cylinder" in text
