from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.repair import Repair, RepairKind

DAY = date(2024, 6, 14)


def a_repair(**changes: object) -> Repair:
    base: dict[str, object] = {
        "cylinder_key": "NCI/A4471",
        "kind": RepairKind.CLEANING,
        "performed_on": DAY,
        "technician_badge": "JT7",
    }
    base.update(changes)
    return Repair(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("valve", RepairKind.VALVE_REPLACEMENT),
        ("threads", RepairKind.NECK_THREAD_REPAIR),
        ("remark", RepairKind.REMARKING),
        ("tumble", RepairKind.TUMBLING),
        ("heat treat", RepairKind.HEAT_TREATMENT),
        ("weld_repair", RepairKind.WELD_REPAIR),
    ],
)
def test_repair_shorthand(text: str, expected: RepairKind) -> None:
    assert RepairKind.parse(text) is expected


def test_an_unknown_repair_lists_what_is_done() -> None:
    with pytest.raises(ValidationError, match="the shop does"):
        RepairKind.parse("polishing")


def test_which_repairs_touch_the_metal() -> None:
    assert RepairKind.WELD_REPAIR.touches_the_pressure_envelope
    assert RepairKind.HEAT_TREATMENT.needs_a_requalification_after
    assert not RepairKind.PAINTING.touches_the_pressure_envelope
    assert not RepairKind.VALVE_REPLACEMENT.needs_a_requalification_after


def test_work_on_the_envelope_needs_a_rin() -> None:
    with pytest.raises(ValidationError, match="under a requalifier's number"):
        a_repair(kind=RepairKind.WELD_REPAIR)
    assert a_repair(kind=RepairKind.WELD_REPAIR, facility_rin="A419").facility_rin == "A419"


def test_a_valve_change_names_the_valve() -> None:
    with pytest.raises(ValidationError, match="what valve went in"):
        a_repair(kind=RepairKind.VALVE_REPLACEMENT)
    changed = a_repair(kind=RepairKind.VALVE_REPLACEMENT, parts="CGA 580 brass")
    assert "CGA 580 brass" in changed.summary()


def test_summaries_read_like_the_shop_log() -> None:
    assert a_repair(note="water blast").summary() == ("2024-06-14 NCI/A4471 cleaning (water blast)")
    assert a_repair().summary() == "2024-06-14 NCI/A4471 cleaning"


def test_labels() -> None:
    assert RepairKind.NECK_THREAD_REPAIR.label == "neck thread repair"
