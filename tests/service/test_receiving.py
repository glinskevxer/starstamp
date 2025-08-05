from datetime import date

import pytest

from starstamp.errors import ConflictError
from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.model.defect import DefectKind
from starstamp.model.lot import LotStatus
from starstamp.model.owner import OwnerAccount
from starstamp.service.receiving import ReceivingService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.owners import OwnerRepository

from ..support.factories import make_cylinder, make_observation
from ..support.requests import requalify
from ..support.shop import stock

KEY = CylinderKey("NCI", "A4471")
RECEIVED = date(2024, 6, 3)


def test_receiving_books_the_lot_and_moves_the_cylinders(shop_book: Book) -> None:
    standing = ReceivingService(shop_book).receive(
        "WELD1", RECEIVED, [KEY], promised_on=date(2024, 6, 28), carrier="Mountain Freight"
    )
    assert standing.lot.number == "L2024-0001"
    assert standing.outstanding == 1
    assert CylinderRepository(shop_book.connection).by_key(KEY).status is CylinderStatus.IN_SHOP


def test_a_cylinder_belonging_to_somebody_else(shop_book: Book) -> None:
    owners = OwnerRepository(shop_book.connection)
    owners.add(OwnerAccount(code="FIRE7", name="Sanpete Fire", opened_on=date(2020, 1, 1)))
    with pytest.raises(ConflictError, match="belongs to WELD1"):
        ReceivingService(shop_book).receive("FIRE7", RECEIVED, [KEY])


def test_a_requalification_settles_the_line(shop_book: Book) -> None:
    service = ReceivingService(shop_book)
    service.receive("WELD1", RECEIVED, [KEY])
    requalify(shop_book)
    standing = service.standing("L2024-0001")
    assert standing.is_finished
    assert standing.lines[0].disposition == "requalified"
    assert standing.lot.status is LotStatus.IN_PROGRESS


def test_a_condemnation_settles_the_line_too(shop_book: Book) -> None:
    service = ReceivingService(shop_book)
    service.receive("WELD1", RECEIVED, [KEY])
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    assert service.standing("L2024-0001").lines[0].disposition == "condemned"


def test_a_lot_is_not_ready_while_anything_is_outstanding(shop_book: Book) -> None:
    service = ReceivingService(shop_book)
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    service.receive("WELD1", RECEIVED, [KEY, other])
    requalify(shop_book)
    with pytest.raises(ConflictError, match="1 cylinders with nothing decided"):
        service.ready("L2024-0001")


def test_a_finished_lot_goes_ready_then_back(shop_book: Book) -> None:
    service = ReceivingService(shop_book)
    service.receive("WELD1", RECEIVED, [KEY])
    requalify(shop_book)
    ready = service.ready("L2024-0001")
    assert ready.lot.status is LotStatus.READY
    returned = service.return_lot("L2024-0001", date(2024, 6, 20))
    assert returned.lot.status is LotStatus.RETURNED
    assert CylinderRepository(shop_book.connection).by_key(KEY).status is CylinderStatus.IN_SERVICE


def test_a_lot_cannot_go_back_before_it_is_ready(shop_book: Book) -> None:
    service = ReceivingService(shop_book)
    service.receive("WELD1", RECEIVED, [KEY])
    with pytest.raises(ConflictError, match="not ready to go back"):
        service.return_lot("L2024-0001", date(2024, 6, 20))


def test_the_standing_line_reads_for_the_counter(shop_book: Book) -> None:
    service = ReceivingService(shop_book)
    service.receive("WELD1", RECEIVED, [KEY], promised_on=date(2024, 6, 10))
    described = service.standing("L2024-0001").describe(date(2024, 6, 15))
    assert "0 of 1 settled" in described
    assert "12 days in the shop" in described
    assert "5 days past the promise" in described


def test_open_lots_come_back_with_their_lines(shop_book: Book) -> None:
    service = ReceivingService(shop_book)
    service.receive("WELD1", RECEIVED, [KEY])
    assert len(service.open_standing()) == 1
    requalify(shop_book)
    service.ready("L2024-0001")
    service.return_lot("L2024-0001", date(2024, 6, 20))
    assert service.open_standing() == []


def test_a_cylinder_not_on_any_lot_settles_nothing(shop_book: Book) -> None:
    requalify(shop_book)
    assert ReceivingService(shop_book).open_standing() == []


def test_a_lot_that_is_ready_takes_no_more_cylinders(shop_book: Book) -> None:
    service = ReceivingService(shop_book)
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    service.receive("WELD1", RECEIVED, [KEY])
    requalify(shop_book)
    service.ready("L2024-0001")
    with pytest.raises(ConflictError, match="takes no more cylinders"):
        service.lots.add_line("L2024-0001", service.cylinders.id_of(other), other, RECEIVED)


def test_a_cylinder_already_in_the_shop_stays_where_it_is(shop_book: Book) -> None:
    cylinders = CylinderRepository(shop_book.connection)
    cylinders.set_status(KEY, CylinderStatus.AWAITING_REPAIR)
    ReceivingService(shop_book).receive("WELD1", RECEIVED, [KEY])
    assert cylinders.by_key(KEY).status is CylinderStatus.AWAITING_REPAIR


def test_settling_reads_only_the_open_lots(shop_book: Book) -> None:
    service = ReceivingService(shop_book)
    service.receive("WELD1", RECEIVED, [KEY])
    requalify(shop_book)
    service.ready("L2024-0001")
    service.return_lot("L2024-0001", date(2024, 6, 20))
    events = service.lots.lines("L2024-0001")
    assert events[0].is_settled
    assert service.open_standing() == []


def test_a_lot_with_nothing_on_it_is_never_finished(shop_book: Book) -> None:
    service = ReceivingService(shop_book)
    service.receive("WELD1", RECEIVED, [])
    standing = service.standing("L2024-0001")
    assert not standing.is_finished
    with pytest.raises(ConflictError, match="nothing decided"):
        service.ready("L2024-0001")
