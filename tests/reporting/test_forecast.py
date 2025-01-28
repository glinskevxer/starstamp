from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.method import Method
from starstamp.model.money import Money
from starstamp.model.pricing import PriceItem
from starstamp.reporting import forecast
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.db import Book
from starstamp.store.pricing import PriceRepository

from ..support.factories import make_cylinder, make_readings
from ..support.shop import DAY, SYSTEM, stock

KEY = CylinderKey("NCI", "A4471")


def priced(book: Book) -> None:
    PriceRepository(book.connection).add(
        PriceItem(
            code="REQUAL_WJ",
            description="water jacket requalification",
            amount=Money.parse("14.50"),
            effective_from=date(2023, 1, 1),
        )
    )


def requalify(book: Book, key: CylinderKey = KEY) -> None:
    RequalificationService(book).perform(
        RequalificationRequest(
            key=key,
            day=DAY,
            technician_badge="JT7",
            method=Method.VOLUMETRIC,
            system_code=SYSTEM,
            readings=make_readings(),
        )
    )


def test_a_book_with_nothing_requalified(shop_book: Book) -> None:
    built = forecast.build(shop_book, DAY, 24)
    assert built.months == ()
    assert built.cylinders == 0
    assert "nothing falls due" in forecast.render(built)


def test_one_cylinder_lands_in_its_month(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book)
    built = forecast.build(shop_book, date(2034, 1, 1), 12)
    assert built.cylinders == 1
    assert built.months[0].month.long_form() == "2034-06"
    assert built.value == Money.parse("14.50")


def test_the_horizon_cuts_it_off(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book)
    assert forecast.build(shop_book, date(2034, 1, 1), 3).months == ()


def test_an_overdue_cylinder_is_counted_separately(shop_book: Book) -> None:
    priced(shop_book)
    requalify(shop_book)
    built = forecast.build(shop_book, date(2035, 1, 1), 24)
    assert built.overdue == 1
    assert built.cylinders == 0
    assert "already out of test" in built.describe()


def test_the_busiest_month_breaks_down_by_account(shop_book: Book) -> None:
    priced(shop_book)
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    requalify(shop_book)
    requalify(shop_book, other)
    built = forecast.build(shop_book, date(2034, 1, 1), 12)
    busiest = built.busiest()
    assert busiest is not None
    assert busiest.cylinders == 2
    assert busiest.by_owner == {"WELD1": 2}
    text = forecast.render(built)
    assert "2034-06 by account" in text
    assert "WELD1 2" in text


def test_an_unpriced_code_forecasts_at_nothing(shop_book: Book) -> None:
    requalify(shop_book)
    built = forecast.build(shop_book, date(2034, 1, 1), 12)
    assert built.cylinders == 1
    assert built.value == Money.zero()


def test_a_condemned_cylinder_is_not_forecast(shop_book: Book) -> None:
    from starstamp.model.cylinder import CylinderStatus
    from starstamp.store.cylinders import CylinderRepository

    priced(shop_book)
    requalify(shop_book)
    CylinderRepository(shop_book.connection).set_status(KEY, CylinderStatus.CONDEMNED)
    assert forecast.build(shop_book, date(2034, 1, 1), 12).cylinders == 0


def test_an_agreed_price_shows_in_the_value(shop_book: Book) -> None:
    from starstamp.model.contract import ContractTerm
    from starstamp.store.contracts import ContractRepository
    from starstamp.store.owners import OwnerRepository

    priced(shop_book)
    requalify(shop_book)
    ContractRepository(shop_book.connection).add(
        ContractTerm(
            owner_code="WELD1",
            code="REQUAL_WJ",
            effective_from=date(2023, 1, 1),
            amount=Money.parse("12.00"),
        ),
        OwnerRepository(shop_book.connection).id_of("WELD1"),
    )
    built = forecast.build(shop_book, date(2034, 1, 1), 12)
    assert built.value == Money.parse("12.00")
