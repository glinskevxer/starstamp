from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.model.defect import DefectKind
from starstamp.model.method import Method
from starstamp.model.repair import RepairKind
from starstamp.service.repair import RepairService
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book

from ..support.factories import make_observation, make_readings
from ..support.shop import DAY, SYSTEM

KEY = CylinderKey("NCI", "A4471")
LATER = date(2024, 6, 14)


def requalify(book: Book, **changes: object) -> None:
    base: dict[str, object] = {
        "key": KEY,
        "day": DAY,
        "technician_badge": "JT7",
        "method": Method.VOLUMETRIC,
        "system_code": SYSTEM,
        "readings": make_readings(),
    }
    base.update(changes)
    RequalificationService(book).perform(RequalificationRequest(**base))  # type: ignore[arg-type]


def test_ordinary_work_leaves_the_cylinder_where_it_was(shop_book: Book) -> None:
    outcome = RepairService(shop_book).perform(
        KEY, RepairKind.PAINTING, LATER, "JT7", note="repaint the collar"
    )
    assert not outcome.needs_requalification
    assert outcome.cleared is None
    assert outcome.status_after is CylinderStatus.IN_SERVICE


def test_a_repair_that_touches_the_metal_sends_it_back_to_the_rig(shop_book: Book) -> None:
    outcome = RepairService(shop_book).perform(KEY, RepairKind.HEAT_TREATMENT, LATER, "JT7")
    assert outcome.needs_requalification
    assert outcome.repair.facility_rin == "A419"
    assert CylinderRepository(shop_book.connection).by_key(KEY).status is CylinderStatus.IN_SHOP
    assert "requalify before filling" in outcome.describe()


def test_a_repair_clears_a_suspension(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.THREAD_DAMAGE),))
    service = RepairService(shop_book)
    held = service.held_by(KEY)
    assert held is not None
    outcome = service.perform(KEY, RepairKind.NECK_THREAD_REPAIR, LATER, "JT7")
    assert outcome.cleared is not None
    assert outcome.cleared.event_id == held.event_id
    assert "clears the hold from 2024-06-12" in outcome.describe()
    assert outcome.status_after is CylinderStatus.IN_SHOP


def test_painting_does_not_clear_a_hold(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.THREAD_DAMAGE),))
    outcome = RepairService(shop_book).perform(KEY, RepairKind.PAINTING, LATER, "JT7")
    assert outcome.cleared is None
    assert not outcome.needs_requalification


def test_a_pass_since_the_hold_means_there_is_nothing_to_clear(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.THREAD_DAMAGE),))
    CylinderRepository(shop_book.connection).set_status(KEY, CylinderStatus.IN_SHOP)
    requalify(shop_book)
    assert RepairService(shop_book).held_by(KEY) is None


def test_a_repair_the_cylinder_does_not_take(shop_book: Book) -> None:
    with pytest.raises(RuleViolationError, match="condemns it"):
        RepairService(shop_book).perform(KEY, RepairKind.WELD_REPAIR, LATER, "JT7")


def test_a_repair_under_a_lapsed_number(shop_book: Book) -> None:
    with pytest.raises(RuleViolationError, match="not in force on 2027-01-04"):
        RepairService(shop_book).perform(KEY, RepairKind.HEAT_TREATMENT, date(2027, 1, 4), "JT7")


def test_a_condemned_cylinder_is_not_repaired(shop_book: Book) -> None:
    CylinderRepository(shop_book.connection).set_status(KEY, CylinderStatus.CONDEMNED)
    with pytest.raises(RuleViolationError, match="is not repaired"):
        RepairService(shop_book).perform(KEY, RepairKind.PAINTING, LATER, "JT7")


def test_the_history_comes_back_in_order(shop_book: Book) -> None:
    service = RepairService(shop_book)
    service.perform(KEY, RepairKind.CLEANING, date(2023, 5, 1), "JT7")
    service.perform(KEY, RepairKind.PAINTING, LATER, "JT7")
    assert [item.kind for item in service.history(KEY)] == [
        RepairKind.CLEANING,
        RepairKind.PAINTING,
    ]


def test_a_valve_change_records_the_valve(shop_book: Book) -> None:
    outcome = RepairService(shop_book).perform(
        KEY, RepairKind.VALVE_REPLACEMENT, LATER, "JT7", parts="CGA 580 brass"
    )
    assert "CGA 580 brass" in outcome.describe()
