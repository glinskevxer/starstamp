import pytest

from starstamp.errors import RuleViolationError, ValidationError
from starstamp.model.cylinder import Cylinder
from starstamp.model.specification import parse_specification
from starstamp.model.ultrasonic import Position, Reading, Scan
from starstamp.rules.pressure_test import Verdict
from starstamp.rules.ultrasonic import (
    check_scan_is_an_examination,
    design_minimum,
    evaluate,
)

from ..support.factories import make_cylinder

ALUMINIUM = parse_specification("DOT-3AL3000")


def a_cylinder(wall: int | None = 220) -> Cylinder:
    return make_cylinder(
        specification=ALUMINIUM,
        nominal_wall_thousandths_in=wall,
        wall_source=None if wall is None else "data sheet",
    )


def a_scan(*pairs: tuple[str, int]) -> Scan:
    return Scan(tuple(Reading(Position.parse(name), value) for name, value in pairs))


def full_scan(value: int = 215) -> Scan:
    return a_scan(
        ("S1", value),
        ("U1", value),
        ("U2", value),
        ("M1", value),
        ("M2", value),
        ("L1", value),
    )


def test_the_design_minimum_is_nine_tenths_of_nominal() -> None:
    assert design_minimum(a_cylinder()) == 198


def test_a_cylinder_with_no_wall_cannot_be_examined() -> None:
    with pytest.raises(ValidationError, match="no recorded wall"):
        design_minimum(a_cylinder(None))


def test_a_healthy_scan_passes() -> None:
    outcome = evaluate(a_cylinder(), full_scan())
    assert outcome.passed
    assert outcome.describe() == "pass"


def test_a_thin_point_condemns() -> None:
    scan = a_scan(("S1", 215), ("U1", 215), ("U2", 197), ("M1", 215), ("M2", 215), ("L1", 215))
    outcome = evaluate(a_cylinder(), scan)
    assert outcome.verdict is Verdict.CONDEMN
    assert "U2 0.197 in is under the 0.198 in design minimum" in outcome.reasons[0]


def test_a_point_just_above_the_floor_is_worth_watching() -> None:
    outcome = evaluate(a_cylinder(), full_scan(200))
    assert outcome.passed
    assert len(outcome.watch) == 6
    assert "watch:" in outcome.describe()


def test_a_scan_with_too_few_points() -> None:
    with pytest.raises(RuleViolationError, match="at least 6 points"):
        check_scan_is_an_examination(a_scan(("M1", 215), ("M2", 215)))


def test_a_scan_that_only_looked_at_one_band() -> None:
    scan = a_scan(("M1", 215), ("M2", 215), ("M3", 215), ("M4", 215), ("M5", 215), ("M6", 215))
    with pytest.raises(RuleViolationError, match="at least 3 bands"):
        check_scan_is_an_examination(scan)


def test_a_steel_cylinder_is_not_examined_this_way() -> None:
    steel = make_cylinder(nominal_wall_thousandths_in=220, wall_source="data sheet")
    with pytest.raises(RuleViolationError, match="not examined ultrasonically"):
        evaluate(steel, full_scan())


def test_the_refusal_for_no_wall_is_not_a_condemnation() -> None:
    with pytest.raises(ValidationError):
        evaluate(a_cylinder(None), full_scan())
