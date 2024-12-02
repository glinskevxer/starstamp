from datetime import date

import pytest

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.disposal import Disposal, DisposalMethod
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.disposals import DisposalRepository
from starstamp.store.owners import OwnerRepository

from ..support.factories import make_cylinder

KEY = CylinderKey("NCI", "A4471")
CONDEMNED = date(2024, 6, 12)


@pytest.fixture
def disposals(
    book: Book, owners: OwnerRepository, cylinders: CylinderRepository
) -> DisposalRepository:
    cylinders.add(make_cylinder(key=KEY), owners.id_of("WELD1"), date(2024, 1, 2))
    return DisposalRepository(book.connection)


def a_disposal(**changes: object) -> Disposal:
    base: dict[str, object] = {
        "cylinder_key": str(KEY),
        "method": DisposalMethod.DRILLED,
        "performed_on": date(2024, 6, 20),
        "technician_badge": "JT7",
        "condemned_on": CONDEMNED,
    }
    base.update(changes)
    return Disposal(**base)  # type: ignore[arg-type]


def test_a_disposal_round_trips(
    disposals: DisposalRepository, cylinders: CylinderRepository
) -> None:
    written = disposals.add(
        a_disposal(scrap_ticket="SC-4411", witness_badge="MR2"), cylinders.id_of(KEY), None
    )
    assert written.disposal_id is not None
    read_back = disposals.by_id(written.disposal_id)
    assert read_back.method is DisposalMethod.DRILLED
    assert read_back.scrap_ticket == "SC-4411"
    assert read_back.witness_badge == "MR2"
    assert read_back.cylinder_key == "NCI/A4471"


def test_a_cylinder_is_dealt_with_once(
    disposals: DisposalRepository, cylinders: CylinderRepository
) -> None:
    disposals.add(a_disposal(), cylinders.id_of(KEY), None)
    with pytest.raises(ConflictError, match="already been dealt with"):
        disposals.add(a_disposal(), cylinders.id_of(KEY), None)


def test_looking_one_up_by_cylinder(
    disposals: DisposalRepository, cylinders: CylinderRepository
) -> None:
    assert disposals.for_cylinder(KEY) is None
    disposals.add(a_disposal(), cylinders.id_of(KEY), None)
    found = disposals.for_cylinder(KEY)
    assert found is not None
    assert found.technician_badge == "JT7"


def test_windows_and_held_cylinders(
    disposals: DisposalRepository, cylinders: CylinderRepository
) -> None:
    disposals.add(a_disposal(method=DisposalMethod.HELD_FOR_OWNER), cylinders.id_of(KEY), None)
    assert len(disposals.between(date(2024, 6, 1), date(2024, 6, 30))) == 1
    assert len(disposals.between(date(2024, 7, 1), date(2024, 7, 31))) == 0
    assert len(disposals.held_for_owners()) == 1
    assert disposals.count() == 1


def test_a_missing_disposal(disposals: DisposalRepository) -> None:
    with pytest.raises(NotFoundError, match="no disposal 99"):
        disposals.by_id(99)
