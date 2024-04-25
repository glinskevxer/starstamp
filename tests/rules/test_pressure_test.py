from fractions import Fraction

import pytest

from starstamp.errors import RuleViolationError, ValidationError
from starstamp.model.cylinder import Cylinder, CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.model.method import Method
from starstamp.model.service import AMMONIA, NITROGEN
from starstamp.model.specification import parse_specification
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion, Pressure
from starstamp.rules.pressure_test import Verdict, evaluate, permanent_limit


def a_cylinder(**changes: object) -> Cylinder:
    base: dict[str, object] = {
        "key": CylinderKey.of("NCI", "A4471"),
        "specification": parse_specification("DOT-3AA2015"),
        "manufactured": StampedMonth(1998, 6),
        "service": NITROGEN,
        "owner_code": "WELD1",
        "rejection_elastic_expansion": Expansion.parse("125.0"),
    }
    base.update(changes)
    return Cylinder(**base)  # type: ignore[arg-type]


def readings(**changes: object) -> PressureReadings:
    base: dict[str, object] = {
        "applied": Pressure(3358),
        "hold_seconds": 30,
        "total_expansion": Expansion.parse("120.0"),
        "permanent_expansion": Expansion.parse("6.0"),
    }
    base.update(changes)
    return PressureReadings(**base)  # type: ignore[arg-type]


def test_a_sound_cylinder_passes() -> None:
    outcome = evaluate(a_cylinder(), Method.VOLUMETRIC, readings())
    assert outcome.passed
    assert outcome.describe() == "pass"


def test_five_percent_permanent_is_on_the_line_for_3aa() -> None:
    at_ten = readings(
        total_expansion=Expansion.parse("120.0"), permanent_expansion=Expansion.parse("12.0")
    )
    assert evaluate(a_cylinder(), Method.VOLUMETRIC, at_ten).passed
    past_ten = readings(
        total_expansion=Expansion.parse("120.0"), permanent_expansion=Expansion.parse("12.1")
    )
    outcome = evaluate(a_cylinder(), Method.VOLUMETRIC, past_ten)
    assert outcome.verdict is Verdict.CONDEMN
    assert "past the 10% limit" in outcome.describe()


def test_high_strength_steel_is_held_to_half_of_that() -> None:
    high_strength = a_cylinder(
        specification=parse_specification("DOT-3HT1850"),
        rejection_elastic_expansion=Expansion.parse("125.0"),
    )
    assert permanent_limit(high_strength) == Fraction(5)
    borderline = readings(
        applied=Pressure(3083),
        total_expansion=Expansion.parse("120.0"),
        permanent_expansion=Expansion.parse("6.1"),
    )
    outcome = evaluate(high_strength, Method.VOLUMETRIC, borderline)
    assert outcome.verdict is Verdict.CONDEMN
    assert "past the 5% limit" in outcome.describe()


def test_the_marked_rejection_limit_condemns_a_cylinder_that_stretched_too_far() -> None:
    stretched = readings(
        total_expansion=Expansion.parse("131.0"), permanent_expansion=Expansion.parse("5.0")
    )
    outcome = evaluate(a_cylinder(), Method.VOLUMETRIC, stretched)
    assert outcome.verdict is Verdict.CONDEMN
    assert "past the marked 125.0 cc" in outcome.describe()


def test_a_cylinder_with_no_marked_limit_is_judged_on_the_percentage_alone() -> None:
    unmarked = a_cylinder(rejection_elastic_expansion=None)
    stretched = readings(
        total_expansion=Expansion.parse("131.0"), permanent_expansion=Expansion.parse("5.0")
    )
    assert evaluate(unmarked, Method.VOLUMETRIC, stretched).passed


def test_both_criteria_can_fire_at_once() -> None:
    bad = readings(
        total_expansion=Expansion.parse("145.0"), permanent_expansion=Expansion.parse("15.0")
    )
    outcome = evaluate(a_cylinder(), Method.VOLUMETRIC, bad)
    assert len(outcome.reasons) == 2


def test_a_leak_condemns_whatever_the_numbers_say() -> None:
    outcome = evaluate(a_cylinder(), Method.VOLUMETRIC, readings(leaked=True))
    assert outcome.verdict is Verdict.CONDEMN
    assert "leaked under pressure" in outcome.reasons


def test_a_proof_test_is_judged_on_leaks_and_set_only() -> None:
    welded = a_cylinder(
        specification=parse_specification("DOT-4BA240"),
        service=AMMONIA,
        rejection_elastic_expansion=None,
    )
    proof = PressureReadings(applied=Pressure(480), hold_seconds=30)
    assert evaluate(welded, Method.PROOF_PRESSURE, proof).passed
    leaking = PressureReadings(applied=Pressure(480), hold_seconds=30, leaked=True)
    assert evaluate(welded, Method.PROOF_PRESSURE, leaking).verdict is Verdict.CONDEMN


def test_expansion_readings_do_not_belong_to_a_proof_test() -> None:
    welded = a_cylinder(
        specification=parse_specification("DOT-4BA240"),
        service=AMMONIA,
        rejection_elastic_expansion=None,
    )
    with pytest.raises(ValidationError, match="belong to another method"):
        evaluate(welded, Method.PROOF_PRESSURE, readings(applied=Pressure(480)))


def test_a_short_hold_is_not_a_test() -> None:
    with pytest.raises(RuleViolationError, match="short of the 30s"):
        evaluate(a_cylinder(), Method.VOLUMETRIC, readings(hold_seconds=25))


def test_a_rig_that_never_reached_test_pressure() -> None:
    with pytest.raises(RuleViolationError, match="short of the required 3358 psig"):
        evaluate(a_cylinder(), Method.VOLUMETRIC, readings(applied=Pressure(3000)))


def test_a_cylinder_taken_far_past_test_pressure_is_out_of_test() -> None:
    with pytest.raises(RuleViolationError, match="out of test rather than tested"):
        evaluate(a_cylinder(), Method.VOLUMETRIC, readings(applied=Pressure(3700)))


def test_ten_percent_over_is_still_a_test() -> None:
    assert evaluate(a_cylinder(), Method.VOLUMETRIC, readings(applied=Pressure(3694))).passed


def test_outcomes_describe_every_reason() -> None:
    bad = readings(
        total_expansion=Expansion.parse("145.0"),
        permanent_expansion=Expansion.parse("15.0"),
        leaked=True,
    )
    described = evaluate(a_cylinder(), Method.VOLUMETRIC, bad).describe()
    assert described.startswith("condemn: leaked under pressure;")
