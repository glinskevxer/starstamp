from datetime import date

from starstamp.model.cylinder import Cylinder, CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import DefectKind, Observation
from starstamp.model.method import Method
from starstamp.model.service import ACETYLENE, AMMONIA, NITROGEN
from starstamp.model.specification import parse_specification
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion, Pressure
from starstamp.rules.marks import plus_eligibility, star_eligibility
from starstamp.rules.pressure_test import PressureOutcome, Verdict
from starstamp.rules.visual import Finding, VisualAssessment, VisualResult

DAY = date(2024, 6, 12)
PASSED = PressureOutcome(Verdict.PASS, ())
FAILED = PressureOutcome(Verdict.CONDEMN, ("leaked under pressure",))
CLEAN = VisualAssessment(())


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
        "total_expansion": Expansion.parse("110.0"),
        "permanent_expansion": Expansion.parse("2.0"),
    }
    base.update(changes)
    return PressureReadings(**base)  # type: ignore[arg-type]


def a_repair_assessment() -> VisualAssessment:
    observation = Observation(kind=DefectKind.THREAD_DAMAGE)
    return VisualAssessment((Finding(observation, VisualResult.REPAIR, "put right"),))


def star(**changes: object) -> object:
    base: dict[str, object] = {
        "cylinder": a_cylinder(),
        "method": Method.VOLUMETRIC,
        "readings": readings(),
        "pressure": PASSED,
        "visual": CLEAN,
        "previous_due": None,
        "day": DAY,
    }
    base.update(changes)
    return star_eligibility(**base)  # type: ignore[arg-type]


def test_a_clean_volumetric_test_earns_a_star() -> None:
    eligibility = star()
    assert eligibility.granted  # type: ignore[attr-defined]
    assert eligibility.describe() == "star granted"  # type: ignore[attr-defined]


def test_a_welded_cylinder_never_gets_one() -> None:
    welded = a_cylinder(
        specification=parse_specification("DOT-4BA240"), rejection_elastic_expansion=None
    )
    refusals = star(cylinder=welded).refusals  # type: ignore[attr-defined]
    assert any("not seamless steel" in reason for reason in refusals)


def test_an_aluminium_cylinder_never_gets_one() -> None:
    aluminium = a_cylinder(specification=parse_specification("DOT-3AL3000"))
    refusals = star(cylinder=aluminium).refusals  # type: ignore[attr-defined]
    assert any("not seamless steel" in reason for reason in refusals)


def test_a_wet_service_refuses_it() -> None:
    wet = a_cylinder(service=AMMONIA)
    refusals = star(cylinder=wet).refusals  # type: ignore[attr-defined]
    assert any("not a dry service" in reason for reason in refusals)


def test_a_service_on_its_own_interval_refuses_it() -> None:
    dissolved = a_cylinder(
        specification=parse_specification("DOT-8AL"),
        service=ACETYLENE,
        rejection_elastic_expansion=None,
    )
    refusals = star(cylinder=dissolved).refusals  # type: ignore[attr-defined]
    assert any("its own interval" in reason for reason in refusals)


def test_a_proof_test_earns_nothing() -> None:
    refusals = star(method=Method.PROOF_PRESSURE, readings=None).refusals  # type: ignore[attr-defined]
    assert any("takes no expansion reading" in reason for reason in refusals)
    assert any("no expansion reading to rest a star on" in reason for reason in refusals)


def test_a_failed_pressure_test_earns_nothing() -> None:
    refusals = star(pressure=FAILED).refusals  # type: ignore[attr-defined]
    assert any("pressure test did not pass" in reason for reason in refusals)


def test_a_repairable_visual_finding_stops_a_star() -> None:
    refusals = star(visual=a_repair_assessment()).refusals  # type: ignore[attr-defined]
    assert any("came back repair" in reason for reason in refusals)


def test_a_cylinder_that_ran_out_of_test_loses_the_star() -> None:
    refusals = star(previous_due=StampedMonth(2024, 5)).refusals  # type: ignore[attr-defined]
    assert any("out of test from 2024-05" in reason for reason in refusals)


def test_a_cylinder_still_in_test_keeps_it() -> None:
    assert star(previous_due=StampedMonth(2024, 6)).granted  # type: ignore[attr-defined]


def test_an_unmarked_cylinder_cannot_be_starred() -> None:
    bare = a_cylinder(rejection_elastic_expansion=None)
    refusals = star(cylinder=bare).refusals  # type: ignore[attr-defined]
    assert any("no marked rejection elastic expansion" in reason for reason in refusals)


def test_a_stretched_cylinder_cannot_be_starred() -> None:
    stretched = readings(
        total_expansion=Expansion.parse("130.0"), permanent_expansion=Expansion.parse("2.0")
    )
    refusals = star(readings=stretched).refusals  # type: ignore[attr-defined]
    assert any("past the marked limit" in reason for reason in refusals)


def test_a_plus_rating_on_a_clean_test() -> None:
    assert plus_eligibility(a_cylinder(), Method.VOLUMETRIC, readings(), PASSED, CLEAN).granted


def test_a_plus_needs_a_water_jacket() -> None:
    eligibility = plus_eligibility(a_cylinder(), Method.DIRECT_EXPANSION, readings(), PASSED, CLEAN)
    assert any("water jacket test" in reason for reason in eligibility.refusals)


def test_a_plus_is_tighter_than_the_condemning_limit() -> None:
    inside_ten = readings(
        total_expansion=Expansion.parse("100.0"), permanent_expansion=Expansion.parse("6.0")
    )
    eligibility = plus_eligibility(a_cylinder(), Method.VOLUMETRIC, inside_ten, PASSED, CLEAN)
    assert not eligibility.granted
    assert any("past the 5%" in reason for reason in eligibility.refusals)


def test_a_plus_wants_clearance_from_the_marked_limit() -> None:
    close = readings(
        total_expansion=Expansion.parse("115.0"), permanent_expansion=Expansion.parse("2.0")
    )
    eligibility = plus_eligibility(a_cylinder(), Method.VOLUMETRIC, close, PASSED, CLEAN)
    assert any("inside a tenth of the marked limit" in reason for reason in eligibility.refusals)


def test_a_plus_on_a_cylinder_with_no_readings() -> None:
    eligibility = plus_eligibility(a_cylinder(), Method.VOLUMETRIC, None, PASSED, CLEAN)
    assert any("rest a plus on" in reason for reason in eligibility.refusals)
    assert eligibility.describe().startswith("plus refused:")


def test_a_plus_on_an_unmarked_cylinder() -> None:
    bare = a_cylinder(rejection_elastic_expansion=None)
    eligibility = plus_eligibility(bare, Method.VOLUMETRIC, readings(), PASSED, CLEAN)
    assert any("no marked rejection" in reason for reason in eligibility.refusals)
