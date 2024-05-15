from datetime import date

from starstamp.model.cylinder import Cylinder
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import DefectKind
from starstamp.model.method import Method
from starstamp.model.service import ACETYLENE, AMMONIA
from starstamp.model.specification import parse_specification
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion
from starstamp.rules.marks import Eligibility, plus_eligibility, star_eligibility
from starstamp.rules.pressure_test import PressureOutcome, Verdict
from starstamp.rules.visual import Finding, VisualAssessment, VisualResult

from ..support.factories import make_cylinder, make_observation, make_readings

DAY = date(2024, 6, 12)
PASSED = PressureOutcome(Verdict.PASS, ())
FAILED = PressureOutcome(Verdict.CONDEMN, ("leaked under pressure",))
CLEAN = VisualAssessment(())


def a_repair_assessment() -> VisualAssessment:
    observation = make_observation(DefectKind.THREAD_DAMAGE)
    return VisualAssessment((Finding(observation, VisualResult.REPAIR, "put right"),))


def star(
    *,
    cylinder: Cylinder | None = None,
    method: Method = Method.VOLUMETRIC,
    readings: PressureReadings | None = None,
    pressure: PressureOutcome | None = PASSED,
    visual: VisualAssessment = CLEAN,
    previous_due: StampedMonth | None = None,
    day: date = DAY,
    with_readings: bool = True,
) -> Eligibility:
    return star_eligibility(
        cylinder or make_cylinder(),
        method,
        readings if readings is not None else (make_readings() if with_readings else None),
        pressure,
        visual,
        previous_due=previous_due,
        day=day,
    )


def test_a_clean_volumetric_test_earns_a_star() -> None:
    eligibility = star()
    assert eligibility.granted
    assert eligibility.describe() == "star granted"


def test_a_welded_cylinder_never_gets_one() -> None:
    welded = make_cylinder(
        specification=parse_specification("DOT-4BA240"), rejection_elastic_expansion=None
    )
    refusals = star(cylinder=welded).refusals
    assert any("not seamless steel" in reason for reason in refusals)


def test_an_aluminium_cylinder_never_gets_one() -> None:
    aluminium = make_cylinder(specification=parse_specification("DOT-3AL3000"))
    refusals = star(cylinder=aluminium).refusals
    assert any("not seamless steel" in reason for reason in refusals)


def test_a_wet_service_refuses_it() -> None:
    wet = make_cylinder(service=AMMONIA)
    refusals = star(cylinder=wet).refusals
    assert any("not a dry service" in reason for reason in refusals)


def test_a_service_on_its_own_interval_refuses_it() -> None:
    dissolved = make_cylinder(
        specification=parse_specification("DOT-8AL"),
        service=ACETYLENE,
        rejection_elastic_expansion=None,
    )
    refusals = star(cylinder=dissolved).refusals
    assert any("its own interval" in reason for reason in refusals)


def test_a_proof_test_earns_nothing() -> None:
    refusals = star(method=Method.PROOF_PRESSURE, with_readings=False).refusals
    assert any("takes no expansion reading" in reason for reason in refusals)
    assert any("no expansion reading to rest a star on" in reason for reason in refusals)


def test_a_failed_pressure_test_earns_nothing() -> None:
    refusals = star(pressure=FAILED).refusals
    assert any("pressure test did not pass" in reason for reason in refusals)


def test_a_repairable_visual_finding_stops_a_star() -> None:
    refusals = star(visual=a_repair_assessment()).refusals
    assert any("came back repair" in reason for reason in refusals)


def test_a_cylinder_that_ran_out_of_test_loses_the_star() -> None:
    refusals = star(previous_due=StampedMonth(2024, 5)).refusals
    assert any("out of test from 2024-05" in reason for reason in refusals)


def test_a_cylinder_still_in_test_keeps_it() -> None:
    assert star(previous_due=StampedMonth(2024, 6)).granted


def test_an_unmarked_cylinder_cannot_be_starred() -> None:
    bare = make_cylinder(rejection_elastic_expansion=None)
    refusals = star(cylinder=bare).refusals
    assert any("no marked rejection elastic expansion" in reason for reason in refusals)


def test_a_stretched_cylinder_cannot_be_starred() -> None:
    stretched = make_readings(
        total_expansion=Expansion.parse("130.0"), permanent_expansion=Expansion.parse("2.0")
    )
    refusals = star(readings=stretched).refusals
    assert any("past the marked limit" in reason for reason in refusals)


def test_a_plus_rating_on_a_clean_test() -> None:
    assert plus_eligibility(
        make_cylinder(), Method.VOLUMETRIC, make_readings(), PASSED, CLEAN
    ).granted


def test_a_plus_needs_a_water_jacket() -> None:
    eligibility = plus_eligibility(
        make_cylinder(), Method.DIRECT_EXPANSION, make_readings(), PASSED, CLEAN
    )
    assert any("water jacket test" in reason for reason in eligibility.refusals)


def test_a_plus_is_tighter_than_the_condemning_limit() -> None:
    inside_ten = make_readings(
        total_expansion=Expansion.parse("100.0"), permanent_expansion=Expansion.parse("6.0")
    )
    eligibility = plus_eligibility(make_cylinder(), Method.VOLUMETRIC, inside_ten, PASSED, CLEAN)
    assert not eligibility.granted
    assert any("past the 5%" in reason for reason in eligibility.refusals)


def test_a_plus_wants_clearance_from_the_marked_limit() -> None:
    close = make_readings(
        total_expansion=Expansion.parse("115.0"), permanent_expansion=Expansion.parse("2.0")
    )
    eligibility = plus_eligibility(make_cylinder(), Method.VOLUMETRIC, close, PASSED, CLEAN)
    assert any("inside a tenth of the marked limit" in reason for reason in eligibility.refusals)


def test_a_plus_on_a_cylinder_with_no_readings() -> None:
    eligibility = plus_eligibility(make_cylinder(), Method.VOLUMETRIC, None, PASSED, CLEAN)
    assert any("rest a plus on" in reason for reason in eligibility.refusals)
    assert eligibility.describe().startswith("plus refused:")


def test_a_plus_on_an_unmarked_cylinder() -> None:
    bare = make_cylinder(rejection_elastic_expansion=None)
    eligibility = plus_eligibility(bare, Method.VOLUMETRIC, make_readings(), PASSED, CLEAN)
    assert any("no marked rejection" in reason for reason in eligibility.refusals)
