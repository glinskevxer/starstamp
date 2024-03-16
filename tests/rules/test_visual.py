import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.defect import DefectKind, Observation
from starstamp.model.service import AMMONIA, NITROGEN
from starstamp.model.specification import parse_specification
from starstamp.rules.visual import VisualResult, assess, judge, limit_for

STEEL = parse_specification("DOT-3AA2015")
ALUMINUM = parse_specification("DOT-3AL3000")
WALL = 220


def observation(kind: DefectKind, **changes: object) -> Observation:
    base: dict[str, object] = {"kind": kind}
    base.update(changes)
    return Observation(**base)  # type: ignore[arg-type]


def test_a_clean_cylinder_passes() -> None:
    assert assess([], STEEL, NITROGEN, WALL).result is VisualResult.PASS


def test_general_corrosion_within_a_tenth_passes() -> None:
    finding = judge(observation(DefectKind.GENERAL_CORROSION, depth_thousandths_in=22), STEEL, WALL)
    assert finding.result is VisualResult.PASS


def test_general_corrosion_past_a_tenth_condemns() -> None:
    finding = judge(observation(DefectKind.GENERAL_CORROSION, depth_thousandths_in=23), STEEL, WALL)
    assert finding.result is VisualResult.CONDEMN
    assert "0.220 in wall" in finding.reason


def test_a_pit_is_allowed_four_times_the_depth_of_general_corrosion() -> None:
    deep = observation(DefectKind.ISOLATED_PITTING, depth_thousandths_in=44)
    assert judge(deep, STEEL, WALL).result is VisualResult.PASS
    deeper = observation(DefectKind.ISOLATED_PITTING, depth_thousandths_in=45)
    assert judge(deeper, STEEL, WALL).result is VisualResult.CONDEMN


def test_a_short_line_of_corrosion_is_judged_as_a_pit() -> None:
    short = observation(
        DefectKind.LINE_CORROSION, depth_thousandths_in=30, length_thousandths_in=2999
    )
    assert limit_for(short).denominator == 5
    assert judge(short, STEEL, WALL).result is VisualResult.PASS


def test_the_same_depth_condemns_once_the_line_runs_three_inches() -> None:
    long_run = observation(
        DefectKind.LINE_CORROSION, depth_thousandths_in=30, length_thousandths_in=3000
    )
    assert limit_for(long_run).denominator == 20
    assert judge(long_run, STEEL, WALL).result is VisualResult.CONDEMN


def test_line_corrosion_without_a_length_cannot_be_judged() -> None:
    bare = observation(DefectKind.LINE_CORROSION, depth_thousandths_in=30)
    with pytest.raises(RuleViolationError, match="without its length"):
        judge(bare, STEEL, WALL)


def test_a_dent_is_judged_against_its_own_width() -> None:
    shallow = observation(DefectKind.DENT, depth_thousandths_in=100, length_thousandths_in=1000)
    assert judge(shallow, STEEL, WALL).result is VisualResult.PASS
    deep = observation(DefectKind.DENT, depth_thousandths_in=101, length_thousandths_in=1000)
    assert judge(deep, STEEL, WALL).result is VisualResult.CONDEMN


def test_a_dent_without_a_width_cannot_be_judged() -> None:
    bare = observation(DefectKind.DENT, depth_thousandths_in=100)
    with pytest.raises(RuleViolationError, match="without its width"):
        judge(bare, STEEL, WALL)


@pytest.mark.parametrize(
    "kind",
    [
        DefectKind.CRACK,
        DefectKind.BULGE,
        DefectKind.LEAK,
        DefectKind.ARC_BURN,
        DefectKind.TORCH_BURN,
    ],
)
def test_the_ones_that_condemn_on_sight(kind: DefectKind) -> None:
    assert judge(observation(kind), STEEL, WALL).result is VisualResult.CONDEMN


@pytest.mark.parametrize(
    "kind",
    [
        DefectKind.NECK_DAMAGE,
        DefectKind.THREAD_DAMAGE,
        DefectKind.ILLEGIBLE_MARKING,
        DefectKind.FOOTRING_DAMAGE,
    ],
)
def test_the_ones_that_are_put_right(kind: DefectKind) -> None:
    assert judge(observation(kind), STEEL, WALL).result is VisualResult.REPAIR


def test_fire_damage_reads_differently_on_steel_and_aluminium() -> None:
    burnt = observation(DefectKind.FIRE_DAMAGE)
    assert judge(burnt, STEEL, WALL).result is VisualResult.REPAIR
    assert judge(burnt, ALUMINUM, WALL).result is VisualResult.CONDEMN


def test_the_worst_finding_carries_the_assessment() -> None:
    assessment = assess(
        [
            observation(DefectKind.THREAD_DAMAGE),
            observation(DefectKind.GENERAL_CORROSION, depth_thousandths_in=10),
            observation(DefectKind.CRACK),
        ],
        STEEL,
        NITROGEN,
        WALL,
    )
    assert assessment.result is VisualResult.CONDEMN
    assert assessment.condemned
    assert not assessment.passes
    assert len(assessment.condemning()) == 1


def test_a_wet_service_has_to_be_looked_at_inside() -> None:
    with pytest.raises(RuleViolationError, match="inspected internally"):
        assess([observation(DefectKind.THREAD_DAMAGE)], STEEL, AMMONIA, WALL)


def test_an_interior_reading_satisfies_it() -> None:
    assessment = assess(
        [observation(DefectKind.INTERIOR_CORROSION, depth_thousandths_in=5)],
        STEEL,
        AMMONIA,
        WALL,
    )
    assert assessment.passes


def test_a_missing_wall_stops_the_judgement() -> None:
    with pytest.raises(RuleViolationError, match="wall thickness"):
        judge(observation(DefectKind.GENERAL_CORROSION, depth_thousandths_in=10), STEEL, 0)


def test_findings_read_as_a_sentence() -> None:
    finding = judge(observation(DefectKind.CRACK), STEEL, WALL)
    assert str(finding) == "condemn: crack (condemned on sight)"
