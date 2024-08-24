from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.repair import RepairKind
from starstamp.model.service import ACETYLENE
from starstamp.model.specification import parse_specification
from starstamp.rules.repair import (
    clears_a_suspension,
    needs_requalification_after,
    permitted_repairs,
    require_permitted,
)

from ..support.factories import make_cylinder

DAY = date(2024, 6, 14)


def test_a_welded_cylinder_may_be_welded() -> None:
    welded = make_cylinder(
        specification=parse_specification("DOT-4BA240"), rejection_elastic_expansion=None
    )
    assert RepairKind.WELD_REPAIR in permitted_repairs(welded)
    assert require_permitted(welded, RepairKind.WELD_REPAIR, DAY) is RepairKind.WELD_REPAIR


def test_a_seamless_cylinder_may_not_be() -> None:
    with pytest.raises(RuleViolationError, match="an arc struck on it condemns it"):
        require_permitted(make_cylinder(), RepairKind.WELD_REPAIR, DAY)


def test_an_aluminium_cylinder_is_never_heat_treated() -> None:
    aluminium = make_cylinder(specification=parse_specification("DOT-3AL3000"))
    with pytest.raises(RuleViolationError, match="not heat treated back into service"):
        require_permitted(aluminium, RepairKind.HEAT_TREATMENT, DAY)


def test_high_strength_steel_is_not_heat_treated_either() -> None:
    high = make_cylinder(
        specification=parse_specification("DOT-3HT1850"), manufactured=StampedMonth(2015, 4)
    )
    with pytest.raises(RuleViolationError, match="not heat treated"):
        require_permitted(high, RepairKind.HEAT_TREATMENT, DAY)


def test_seamless_steel_is() -> None:
    assert require_permitted(make_cylinder(), RepairKind.HEAT_TREATMENT, DAY)


def test_ordinary_work_is_allowed_everywhere() -> None:
    for spec in ("DOT-3AA2015", "DOT-3AL3000", "DOT-4BA240", "DOT-3HT1850"):
        cylinder = make_cylinder(
            specification=parse_specification(spec),
            rejection_elastic_expansion=None,
            manufactured=StampedMonth(2015, 4),
        )
        assert RepairKind.PAINTING in permitted_repairs(cylinder)


def test_an_acetylene_cylinder_takes_almost_nothing() -> None:
    acetylene = make_cylinder(
        specification=parse_specification("DOT-8AL"),
        service=ACETYLENE,
        rejection_elastic_expansion=None,
    )
    with pytest.raises(RuleViolationError, match="it takes"):
        require_permitted(acetylene, RepairKind.TUMBLING, DAY)
    assert require_permitted(acetylene, RepairKind.VALVE_REPLACEMENT, DAY)


def test_a_condemned_cylinder_is_not_repaired() -> None:
    condemned = make_cylinder(status=CylinderStatus.CONDEMNED)
    with pytest.raises(RuleViolationError, match="is not repaired"):
        require_permitted(condemned, RepairKind.PAINTING, DAY)


def test_a_cylinder_past_its_life_is_not_worth_repairing() -> None:
    high = make_cylinder(
        specification=parse_specification("DOT-3HT1850"), manufactured=StampedMonth(2015, 4)
    )
    with pytest.raises(RuleViolationError, match="buys nothing"):
        require_permitted(high, RepairKind.PAINTING, date(2040, 1, 1))


def test_which_repairs_send_a_cylinder_back_to_the_rig() -> None:
    assert needs_requalification_after(RepairKind.WELD_REPAIR)
    assert needs_requalification_after(RepairKind.NECK_THREAD_REPAIR)
    assert not needs_requalification_after(RepairKind.CLEANING)


def test_painting_clears_nothing() -> None:
    assert not clears_a_suspension(RepairKind.PAINTING)
    assert clears_a_suspension(RepairKind.NECK_THREAD_REPAIR)
