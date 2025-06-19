from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.reporting import cycle
from starstamp.service.receiving import ReceivingService
from starstamp.store.db import Book

from ..support.requests import requalify

KEY = CylinderKey("NCI", "A4471")
FIRST = date(2024, 6, 1)
LAST = date(2024, 6, 30)


def a_finished_lot(book: Book, returned_on: date, promised_on: date | None = None) -> None:
    receiving = ReceivingService(book)
    receiving.receive("WELD1", date(2024, 6, 3), [KEY], promised_on=promised_on)
    requalify(book)
    receiving.ready("L2024-0001")
    receiving.return_lot("L2024-0001", returned_on)


def test_a_window_with_no_lots(shop_book: Book) -> None:
    built = cycle.build(shop_book, FIRST, LAST)
    assert built.lots == ()
    assert "no lots went back" in built.describe()
    assert cycle.render(built) == built.describe()


def test_one_lot_through_the_shop(shop_book: Book) -> None:
    a_finished_lot(shop_book, date(2024, 6, 20))
    built = cycle.build(shop_book, FIRST, LAST)
    item = built.finished[0]
    assert item.door_to_door == 17
    assert item.waiting_to_start == 9
    assert item.bench_days == 1
    assert item.waiting_to_go == 8
    assert not item.was_late


def test_a_late_lot_is_flagged(shop_book: Book) -> None:
    a_finished_lot(shop_book, date(2024, 6, 20), promised_on=date(2024, 6, 15))
    built = cycle.build(shop_book, FIRST, LAST)
    assert len(built.late()) == 1
    assert "1 were late" in built.describe()


def test_a_lot_still_in_the_shop_has_no_door_to_door(shop_book: Book) -> None:
    ReceivingService(shop_book).receive("WELD1", date(2024, 6, 3), [KEY])
    built = cycle.build(shop_book, FIRST, LAST)
    assert built.lots[0].door_to_door is None
    assert built.finished == ()


def test_a_lot_nothing_was_done_to(shop_book: Book) -> None:
    receiving = ReceivingService(shop_book)
    receiving.receive("WELD1", date(2024, 6, 3), [KEY])
    built = cycle.build(shop_book, FIRST, LAST)
    assert built.lots[0].bench_days is None
    assert built.lots[0].waiting_to_start is None


def test_the_averages(shop_book: Book) -> None:
    a_finished_lot(shop_book, date(2024, 6, 20))
    built = cycle.build(shop_book, FIRST, LAST)
    assert float(built.average_door_to_door()) == 17.0
    assert float(built.average_waiting_to_start()) == 9.0


def test_rendering(shop_book: Book) -> None:
    a_finished_lot(shop_book, date(2024, 6, 20))
    text = cycle.render(cycle.build(shop_book, FIRST, LAST))
    assert "L2024-0001" in text
    assert "door to door on average" in text
