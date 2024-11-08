import pytest

from starstamp.errors import RuleViolationError, ValidationError
from starstamp.model.acetylene import AcetyleneExam
from starstamp.model.cylinder import Cylinder
from starstamp.model.service import ACETYLENE
from starstamp.model.specification import parse_specification
from starstamp.rules.acetylene import evaluate, loss_limit, marked_tare
from starstamp.rules.pressure_test import Verdict
from starstamp.rules.visual import VisualResult

from ..support.factories import make_cylinder

MARKED = 8500


def a_cylinder(tare: int | None = MARKED) -> Cylinder:
    return make_cylinder(
        specification=parse_specification("DOT-8AL"),
        service=ACETYLENE,
        rejection_elastic_expansion=None,
        tare_hundredths_lb=tare,
        valve_outlet="510",
    )


def test_the_limit_is_one_percent_of_the_marked_tare() -> None:
    assert marked_tare(a_cylinder()) == MARKED
    assert loss_limit(a_cylinder()) == 85


def test_a_cylinder_with_no_marked_tare_cannot_be_weighed() -> None:
    with pytest.raises(RuleViolationError, match="no marked tare weight"):
        marked_tare(a_cylinder(None))


def test_a_steel_cylinder_is_not_examined_this_way() -> None:
    with pytest.raises(RuleViolationError, match="not an acetylene cylinder"):
        marked_tare(make_cylinder())


def test_a_sound_cylinder_passes() -> None:
    outcome = evaluate(a_cylinder(), AcetyleneExam(tare_now_hundredths_lb=8470))
    assert outcome.passed
    assert outcome.loss_hundredths == 30
    assert outcome.describe() == "pass"


def test_the_loss_limit_is_where_it_says() -> None:
    assert evaluate(a_cylinder(), AcetyleneExam(tare_now_hundredths_lb=8415)).passed
    outcome = evaluate(a_cylinder(), AcetyleneExam(tare_now_hundredths_lb=8414))
    assert outcome.verdict is Verdict.CONDEMN
    assert "0.86 lb against its marked tare" in outcome.reasons[0]


def test_a_heavy_cylinder_has_water_in_it() -> None:
    outcome = evaluate(a_cylinder(), AcetyleneExam(tare_now_hundredths_lb=8600))
    assert outcome.verdict is Verdict.CONDEMN
    assert "water in the mass" in outcome.reasons[0]


def test_a_little_over_is_still_a_pass() -> None:
    assert evaluate(a_cylinder(), AcetyleneExam(tare_now_hundredths_lb=8520)).passed


def test_a_settled_mass_condemns() -> None:
    outcome = evaluate(a_cylinder(), AcetyleneExam(tare_now_hundredths_lb=8470, mass_settled=True))
    assert outcome.verdict is Verdict.CONDEMN
    assert "left a void" in outcome.reasons[0]


def test_an_unsound_shell_condemns() -> None:
    outcome = evaluate(a_cylinder(), AcetyleneExam(tare_now_hundredths_lb=8470, shell_sound=False))
    assert outcome.result is VisualResult.CONDEMN


def test_bad_plugs_are_a_repair_not_a_condemnation() -> None:
    outcome = evaluate(
        a_cylinder(), AcetyleneExam(tare_now_hundredths_lb=8470, fuse_plugs_sound=False)
    )
    assert outcome.verdict is Verdict.PASS
    assert outcome.result is VisualResult.REPAIR
    assert not outcome.passed
    assert "fusible plugs" in outcome.describe()


def test_a_bad_cap_is_also_a_repair() -> None:
    outcome = evaluate(a_cylinder(), AcetyleneExam(tare_now_hundredths_lb=8470, cap_sound=False))
    assert outcome.result is VisualResult.REPAIR


def test_condemnation_beats_repair() -> None:
    outcome = evaluate(
        a_cylinder(),
        AcetyleneExam(tare_now_hundredths_lb=8000, fuse_plugs_sound=False),
    )
    assert outcome.result is VisualResult.CONDEMN
    assert len(outcome.reasons) == 1


def test_a_weighing_of_nothing() -> None:
    with pytest.raises(ValidationError, match="not a weighing"):
        AcetyleneExam(tare_now_hundredths_lb=0)


def test_the_exam_describes_itself() -> None:
    exam = AcetyleneExam(
        tare_now_hundredths_lb=8470,
        fuse_plugs_sound=False,
        mass_settled=True,
        shell_sound=False,
        cap_sound=False,
        note="rust at the foot",
    )
    described = exam.describe()
    assert "tare 84.70 lb" in described
    assert "mass settled" in described
    assert "rust at the foot" in described
