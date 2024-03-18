from datetime import date

import pytest

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.cylinder import Cylinder, CylinderKey, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.owner import OwnerAccount
from starstamp.model.service import ARGON, NITROGEN, OXYGEN
from starstamp.model.specification import parse_specification
from starstamp.model.units import Expansion
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.owners import OwnerRepository

RECORDED = date(2024, 3, 1)


def a_cylinder(serial: str = "A4471", **changes: object) -> Cylinder:
    base: dict[str, object] = {
        "key": CylinderKey.of("NCI", serial),
        "specification": parse_specification("DOT-3AA2015"),
        "manufactured": StampedMonth(1998, 6),
        "service": NITROGEN,
        "owner_code": "WELD1",
        "rejection_elastic_expansion": Expansion.parse("31.2"),
        "water_capacity_tenths_l": 435,
        "tare_hundredths_lb": 11750,
    }
    base.update(changes)
    return Cylinder(**base)  # type: ignore[arg-type]


def test_round_trip(cylinders: CylinderRepository, owners: OwnerRepository) -> None:
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    found = cylinders.by_key(CylinderKey.of("NCI", "A4471"))
    assert found.specification.code == "3AA"
    assert found.service is NITROGEN
    assert found.owner_code == "WELD1"
    assert found.require_ree() == Expansion.parse("31.2")
    assert found.water_capacity_tenths_l == 435


def test_the_stamped_marking_survives(
    cylinders: CylinderRepository, owners: OwnerRepository
) -> None:
    permit = a_cylinder("SP9", specification=parse_specification("DOT-SP 14456"))
    cylinders.add(permit, owners.id_of("WELD1"), RECORDED)
    found = cylinders.by_key(CylinderKey.of("NCI", "SP9"))
    assert str(found.specification) == "DOT-SP 14456"


def test_duplicates_are_refused(cylinders: CylinderRepository, owners: OwnerRepository) -> None:
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    with pytest.raises(ConflictError, match="already on the books"):
        cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)


def test_two_makers_may_share_a_serial(
    cylinders: CylinderRepository, owners: OwnerRepository
) -> None:
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    other = a_cylinder(key=CylinderKey.of("PST", "A4471"))
    cylinders.add(other, owners.id_of("WELD1"), RECORDED)
    assert cylinders.count() == 2


def test_missing_cylinder(cylinders: CylinderRepository) -> None:
    with pytest.raises(NotFoundError, match="no cylinder NCI/NOPE"):
        cylinders.by_key(CylinderKey.of("NCI", "NOPE"))


def test_ids_map_both_ways(cylinders: CylinderRepository, owners: OwnerRepository) -> None:
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    key = CylinderKey.of("NCI", "A4471")
    assert cylinders.key_of(cylinders.id_of(key)) == key
    with pytest.raises(NotFoundError):
        cylinders.key_of(4242)


def test_exists(cylinders: CylinderRepository, owners: OwnerRepository) -> None:
    key = CylinderKey.of("NCI", "A4471")
    assert not cylinders.exists(key)
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    assert cylinders.exists(key)


def test_listing_by_owner_and_service(
    cylinders: CylinderRepository, owners: OwnerRepository
) -> None:
    owners.add(OwnerAccount(code="FIRE7", name="Sanpete Fire", opened_on=date(2020, 1, 1)))
    cylinders.add(a_cylinder("A1"), owners.id_of("WELD1"), RECORDED)
    cylinders.add(a_cylinder("A2", service=ARGON), owners.id_of("WELD1"), RECORDED)
    cylinders.add(a_cylinder("A3", service=OXYGEN), owners.id_of("FIRE7"), RECORDED)
    assert [c.key.serial for c in cylinders.for_owner("WELD1")] == ["A1", "A2"]
    assert [c.key.serial for c in cylinders.in_service_of(OXYGEN)] == ["A3"]


def test_status_moves_and_listing(cylinders: CylinderRepository, owners: OwnerRepository) -> None:
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    key = CylinderKey.of("NCI", "A4471")
    cylinders.set_status(key, CylinderStatus.IN_SHOP)
    assert [c.key for c in cylinders.with_status(CylinderStatus.IN_SHOP)] == [key]
    cylinders.set_status(key, CylinderStatus.CONDEMNED)
    with pytest.raises(NotFoundError, match="takes no more work"):
        cylinders.require(key)


def test_a_condemned_cylinder_does_not_move_back(
    cylinders: CylinderRepository, owners: OwnerRepository
) -> None:
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    key = CylinderKey.of("NCI", "A4471")
    cylinders.set_status(key, CylinderStatus.CONDEMNED)
    with pytest.raises(Exception, match="does not come back"):
        cylinders.set_status(key, CylinderStatus.IN_SERVICE)


def test_transfer_moves_the_owner(cylinders: CylinderRepository, owners: OwnerRepository) -> None:
    owners.add(OwnerAccount(code="FIRE7", name="Sanpete Fire", opened_on=date(2020, 1, 1)))
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    key = CylinderKey.of("NCI", "A4471")
    moved = cylinders.transfer(key, owners.id_of("FIRE7"))
    assert moved.owner_code == "FIRE7"


def test_a_condemned_cylinder_does_not_change_hands(
    cylinders: CylinderRepository, owners: OwnerRepository
) -> None:
    owners.add(OwnerAccount(code="FIRE7", name="Sanpete Fire", opened_on=date(2020, 1, 1)))
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    key = CylinderKey.of("NCI", "A4471")
    cylinders.set_status(key, CylinderStatus.SCRAPPED)
    with pytest.raises(ConflictError, match="cannot change hands"):
        cylinders.transfer(key, owners.id_of("FIRE7"))


def test_a_wall_reading_is_kept_and_carried_forward(
    cylinders: CylinderRepository, owners: OwnerRepository
) -> None:
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    key = CylinderKey.of("NCI", "A4471")
    assert not cylinders.by_key(key).wall_is_known
    updated = cylinders.record_wall(key, date(2024, 4, 2), 220, "data sheet", None)
    assert updated.require_wall() == 220
    assert updated.wall_source == "data sheet"


def test_wall_readings_accumulate(cylinders: CylinderRepository, owners: OwnerRepository) -> None:
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    key = CylinderKey.of("NCI", "A4471")
    cylinders.record_wall(key, date(2024, 4, 2), 220, "data sheet", None)
    cylinders.record_wall(key, date(2025, 4, 2), 214, "ultrasonic sweep", "three points")
    readings = cylinders.wall_readings(key)
    assert [reading[1] for reading in readings] == [220, 214]
    assert cylinders.by_key(key).require_wall() == 214


def test_a_wall_reading_has_to_be_a_measurement(
    cylinders: CylinderRepository, owners: OwnerRepository
) -> None:
    cylinders.add(a_cylinder(), owners.id_of("WELD1"), RECORDED)
    with pytest.raises(ConflictError, match="positive measurement"):
        cylinders.record_wall(CylinderKey.of("NCI", "A4471"), date(2024, 4, 2), 0, "guess", None)
