from datetime import date

import pytest

from starstamp.errors import ConflictError
from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.model.owner import OwnerAccount
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.owners import OwnerRepository
from starstamp.store.transfers import TransferRepository

from ..support.factories import make_cylinder

KEY = CylinderKey("NCI", "A4471")
RECORDED = date(2024, 1, 2)


@pytest.fixture
def moved(book: Book, owners: OwnerRepository, cylinders: CylinderRepository) -> Book:
    owners.add(OwnerAccount(code="FIRE7", name="Sanpete Fire", opened_on=date(2020, 1, 1)))
    cylinders.add(make_cylinder(key=KEY), owners.id_of("WELD1"), RECORDED)
    return book


def test_a_transfer_is_kept(
    moved: Book, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    cylinders.transfer(KEY, owners.id_of("FIRE7"), date(2024, 6, 20), "sold with the business")
    transfers = TransferRepository(moved.connection)
    history = transfers.for_cylinder(KEY)
    assert len(history) == 1
    assert history[0].from_owner == "WELD1"
    assert history[0].to_owner == "FIRE7"
    assert "WELD1 to FIRE7" in history[0].summary()
    assert "sold with the business" in history[0].summary()


def test_who_owned_it_on_a_day(
    moved: Book, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    cylinders.transfer(KEY, owners.id_of("FIRE7"), date(2024, 6, 20))
    transfers = TransferRepository(moved.connection)
    assert transfers.owner_on(KEY, date(2024, 6, 19), "FIRE7") == "WELD1"
    assert transfers.owner_on(KEY, date(2024, 6, 20), "FIRE7") == "FIRE7"
    assert transfers.owner_on(KEY, date(2025, 1, 1), "FIRE7") == "FIRE7"


def test_a_cylinder_that_never_moved(moved: Book) -> None:
    transfers = TransferRepository(moved.connection)
    assert transfers.for_cylinder(KEY) == []
    assert transfers.owner_on(KEY, date(2024, 6, 20), "WELD1") == "WELD1"
    assert transfers.count() == 0


def test_transferring_to_the_owner_it_already_has(
    moved: Book, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    with pytest.raises(ConflictError, match="already belongs to WELD1"):
        cylinders.transfer(KEY, owners.id_of("WELD1"), date(2024, 6, 20))


def test_a_scrapped_cylinder_does_not_move(
    moved: Book, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    cylinders.set_status(KEY, CylinderStatus.CONDEMNED)
    with pytest.raises(ConflictError, match="cannot change hands"):
        cylinders.transfer(KEY, owners.id_of("FIRE7"), date(2024, 6, 20))


def test_transfers_in_a_window(
    moved: Book, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    cylinders.transfer(KEY, owners.id_of("FIRE7"), date(2024, 6, 20))
    transfers = TransferRepository(moved.connection)
    assert len(transfers.between(date(2024, 6, 1), date(2024, 6, 30))) == 1
    assert transfers.between(date(2024, 7, 1), date(2024, 7, 31)) == []
