from datetime import date

import pytest

from starstamp.errors import NotFoundError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.repair import Repair, RepairKind
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.owners import OwnerRepository
from starstamp.store.repairs import RepairRepository

from ..support.factories import make_cylinder

KEY = CylinderKey("NCI", "A4471")
DAY = date(2024, 6, 14)


@pytest.fixture
def repairs(book: Book, owners: OwnerRepository, cylinders: CylinderRepository) -> RepairRepository:
    cylinders.add(make_cylinder(key=KEY), owners.id_of("WELD1"), date(2024, 1, 2))
    return RepairRepository(book.connection)


def a_repair(**changes: object) -> Repair:
    base: dict[str, object] = {
        "cylinder_key": str(KEY),
        "kind": RepairKind.CLEANING,
        "performed_on": DAY,
        "technician_badge": "JT7",
    }
    base.update(changes)
    return Repair(**base)  # type: ignore[arg-type]


def test_a_repair_round_trips(repairs: RepairRepository, cylinders: CylinderRepository) -> None:
    written = repairs.add(a_repair(note="water blast"), cylinders.id_of(KEY))
    assert written.repair_id is not None
    read_back = repairs.by_id(written.repair_id)
    assert read_back.kind is RepairKind.CLEANING
    assert read_back.note == "water blast"
    assert read_back.cylinder_key == "NCI/A4471"


def test_a_valve_change_keeps_its_parts(
    repairs: RepairRepository, cylinders: CylinderRepository
) -> None:
    written = repairs.add(
        a_repair(kind=RepairKind.VALVE_REPLACEMENT, parts="CGA 580 brass"),
        cylinders.id_of(KEY),
    )
    assert written.repair_id is not None
    assert repairs.by_id(written.repair_id).parts == "CGA 580 brass"


def test_history_for_a_cylinder(repairs: RepairRepository, cylinders: CylinderRepository) -> None:
    repairs.add(a_repair(performed_on=date(2023, 1, 4)), cylinders.id_of(KEY))
    repairs.add(a_repair(kind=RepairKind.PAINTING), cylinders.id_of(KEY))
    history = repairs.for_cylinder(KEY)
    assert [item.kind for item in history] == [RepairKind.CLEANING, RepairKind.PAINTING]
    assert repairs.count() == 2


def test_lookups_by_window_and_kind(
    repairs: RepairRepository, cylinders: CylinderRepository
) -> None:
    repairs.add(a_repair(), cylinders.id_of(KEY))
    repairs.add(
        a_repair(kind=RepairKind.PAINTING, performed_on=date(2024, 7, 1)), cylinders.id_of(KEY)
    )
    assert len(repairs.between(date(2024, 6, 1), date(2024, 6, 30))) == 1
    assert len(repairs.of_kind(RepairKind.PAINTING)) == 1


def test_a_repair_can_name_the_record_it_clears(
    repairs: RepairRepository, cylinders: CylinderRepository
) -> None:
    written = repairs.add(a_repair(), cylinders.id_of(KEY), clears_event_id=None)
    assert written.repair_id is not None
    assert repairs.cleared_event_id(written.repair_id) is None
    assert repairs.clearing(4) == []


def test_a_missing_repair(repairs: RepairRepository) -> None:
    with pytest.raises(NotFoundError, match="no repair 99"):
        repairs.by_id(99)
