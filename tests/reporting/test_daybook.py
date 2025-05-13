from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind
from starstamp.model.repair import RepairKind
from starstamp.model.service import NITROGEN
from starstamp.model.units import Pressure
from starstamp.reporting import daybook
from starstamp.service.filling import FillingService
from starstamp.service.receiving import ReceivingService
from starstamp.service.repair import RepairService
from starstamp.store.db import Book

from ..support.factories import make_observation
from ..support.requests import requalify
from ..support.shop import DAY

KEY = CylinderKey("NCI", "A4471")


def test_a_quiet_day(shop_book: Book) -> None:
    book = daybook.build(shop_book, DAY)
    assert book.is_quiet
    assert "nothing happened on 2024-06-12" in book.describe()
    assert daybook.render(book) == book.describe()


def test_a_day_with_a_test_in_it(shop_book: Book) -> None:
    requalify(shop_book)
    book = daybook.build(shop_book, DAY)
    assert not book.is_quiet
    assert book.counts() == {"test": 1}
    assert "volumetric pass" in book.of_kind("test")[0].detail


def test_a_day_with_the_lot_and_the_fill(shop_book: Book) -> None:
    ReceivingService(shop_book).receive("WELD1", DAY, [KEY])
    requalify(shop_book)
    FillingService(shop_book).record(KEY, NITROGEN, DAY, "JT7", pressure=Pressure(2015))
    book = daybook.build(shop_book, DAY)
    assert book.counts() == {"fill": 1, "received": 1, "test": 1}
    assert "1 cylinders" in book.of_kind("received")[0].detail


def test_a_condemnation_says_why(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    book = daybook.build(shop_book, DAY)
    assert "bulge" in book.of_kind("test")[0].detail


def test_repairs_and_transfers_show(shop_book: Book) -> None:
    RepairService(shop_book).perform(KEY, RepairKind.PAINTING, DAY, "JT7")
    book = daybook.build(shop_book, DAY)
    assert book.counts() == {"repair": 1}
    assert book.of_kind("repair")[0].detail == "painting"


def test_a_returned_lot_shows_on_the_day_it_went(shop_book: Book) -> None:
    receiving = ReceivingService(shop_book)
    receiving.receive("WELD1", date(2024, 6, 3), [KEY])
    requalify(shop_book)
    receiving.ready("L2024-0001")
    receiving.return_lot("L2024-0001", date(2024, 6, 20))
    book = daybook.build(shop_book, date(2024, 6, 20))
    assert book.counts() == {}


def test_a_reversed_record_is_marked(shop_book: Book) -> None:
    from starstamp.store.events import EventRepository

    requalify(shop_book)
    EventRepository(shop_book.connection).reverse(1, "wrong cylinder")
    book = daybook.build(shop_book, DAY)
    assert "[reversed]" in book.of_kind("test")[0].detail


def test_rendering(shop_book: Book) -> None:
    requalify(shop_book)
    text = daybook.render(daybook.build(shop_book, DAY))
    assert "2024-06-12: 1 test" in text
    assert "NCI/A4471" in text
