from datetime import date

import pytest

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.lot import Lot, LotStatus
from starstamp.model.owner import OwnerAccount
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.lots import LotRepository
from starstamp.store.owners import OwnerRepository

from ..support.factories import make_cylinder

RECEIVED = date(2024, 6, 3)
KEY = CylinderKey("NCI", "A4471")


@pytest.fixture
def lots(book: Book, owners: OwnerRepository, cylinders: CylinderRepository) -> LotRepository:
    cylinders.add(make_cylinder(key=KEY), owners.id_of("WELD1"), RECEIVED)
    repository = LotRepository(book.connection)
    repository.add(
        Lot(
            number="L2024-0007",
            owner_code="WELD1",
            received_on=RECEIVED,
            promised_on=date(2024, 6, 28),
            carrier="Mountain Freight",
        ),
        owners.id_of("WELD1"),
    )
    return repository


def test_a_lot_round_trips(lots: LotRepository) -> None:
    lot = lots.by_number("l2024-0007")
    assert lot.owner_code == "WELD1"
    assert lot.carrier == "Mountain Freight"
    assert lot.status is LotStatus.RECEIVED


def test_numbers_run_on_from_what_is_there(lots: LotRepository, owners: OwnerRepository) -> None:
    assert lots.next_number(2024) == "L2024-0008"
    assert lots.next_number(2025) == "L2025-0001"


def test_a_duplicate_number(lots: LotRepository, owners: OwnerRepository) -> None:
    with pytest.raises(ConflictError, match="already open"):
        lots.add(
            Lot(number="L2024-0007", owner_code="WELD1", received_on=RECEIVED),
            owners.id_of("WELD1"),
        )


def test_a_missing_lot(lots: LotRepository) -> None:
    with pytest.raises(NotFoundError, match="no lot L2024-9999"):
        lots.by_number("L2024-9999")


def test_lines_are_added_and_read_back(lots: LotRepository, cylinders: CylinderRepository) -> None:
    lots.add_line("L2024-0007", cylinders.id_of(KEY), KEY, RECEIVED)
    lines = lots.lines("L2024-0007")
    assert [line.cylinder_key for line in lines] == ["NCI/A4471"]
    assert lots.open_lines("L2024-0007")


def test_a_cylinder_goes_on_a_lot_once(lots: LotRepository, cylinders: CylinderRepository) -> None:
    lots.add_line("L2024-0007", cylinders.id_of(KEY), KEY, RECEIVED)
    with pytest.raises(ConflictError, match="already on L2024-0007"):
        lots.add_line("L2024-0007", cylinders.id_of(KEY), KEY, RECEIVED)


def test_settling_a_line(lots: LotRepository, cylinders: CylinderRepository) -> None:
    lots.add_line("L2024-0007", cylinders.id_of(KEY), KEY, RECEIVED)
    lots.settle("L2024-0007", cylinders.id_of(KEY), "requalified", None)
    line = lots.lines("L2024-0007")[0]
    assert line.disposition == "requalified"
    assert lots.open_lines("L2024-0007") == []


def test_settling_against_a_record_that_is_not_there(
    lots: LotRepository, cylinders: CylinderRepository
) -> None:
    lots.add_line("L2024-0007", cylinders.id_of(KEY), KEY, RECEIVED)
    with pytest.raises(ConflictError, match="not in this book"):
        lots.settle("L2024-0007", cylinders.id_of(KEY), "requalified", 404)


def test_settling_a_cylinder_that_is_not_on_the_lot(
    lots: LotRepository, cylinders: CylinderRepository
) -> None:
    with pytest.raises(ConflictError, match="not on L2024-0007"):
        lots.settle("L2024-0007", cylinders.id_of(KEY), "requalified", None)


def test_a_returned_lot_takes_no_more_cylinders(
    lots: LotRepository, cylinders: CylinderRepository
) -> None:
    lots.set_status("L2024-0007", LotStatus.RETURNED, date(2024, 6, 20))
    with pytest.raises(ConflictError, match="went back on"):
        lots.set_status("L2024-0007", LotStatus.READY)


def test_a_lot_going_back_needs_its_day(lots: LotRepository) -> None:
    with pytest.raises(ConflictError, match="needs the day it went"):
        lots.set_status("L2024-0007", LotStatus.RETURNED)


def test_a_ready_lot_takes_no_more_cylinders(
    lots: LotRepository, cylinders: CylinderRepository
) -> None:
    lots.set_status("L2024-0007", LotStatus.READY)
    with pytest.raises(ConflictError, match="takes no more cylinders"):
        lots.add_line("L2024-0007", cylinders.id_of(KEY), KEY, RECEIVED)


def test_listings(lots: LotRepository, owners: OwnerRepository) -> None:
    owners.add(OwnerAccount(code="FIRE7", name="Sanpete Fire", opened_on=date(2020, 1, 1)))
    lots.add(
        Lot(number="L2024-0008", owner_code="FIRE7", received_on=date(2024, 6, 10)),
        owners.id_of("FIRE7"),
    )
    assert len(lots.open_lots()) == 2
    assert [lot.number for lot in lots.for_owner("weld1")] == ["L2024-0007"]
    assert len(lots.received_between(date(2024, 6, 1), date(2024, 6, 5))) == 1
    lots.set_status("L2024-0007", LotStatus.RETURNED, date(2024, 6, 20))
    assert len(lots.open_lots()) == 1


def test_which_lots_a_cylinder_has_been_on(
    lots: LotRepository, cylinders: CylinderRepository
) -> None:
    lots.add_line("L2024-0007", cylinders.id_of(KEY), KEY, RECEIVED)
    assert lots.lots_holding(cylinders.id_of(KEY)) == ["L2024-0007"]
