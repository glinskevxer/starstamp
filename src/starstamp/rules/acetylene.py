"""Judging an acetylene cylinder.

The criterion is the cylinder's own marked tare weight, which makes this the
same shape of rule as the ultrasonic one: the number a cylinder is held to
came off the cylinder, and a cylinder without that mark cannot be examined
here at all. The refusal for a missing mark is not a condemnation, because a
shop that condemns everything it cannot read is throwing away good steel.

Weight gain is treated separately from weight loss and is not a pass. A
cylinder heavier than its mark has taken on water, and water in an acetylene
cylinder is worse than a light one.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from starstamp.errors import RuleViolationError
from starstamp.model.acetylene import AcetyleneExam
from starstamp.model.cylinder import Cylinder
from starstamp.model.specification import SpecFamily
from starstamp.rules.pressure_test import Verdict
from starstamp.rules.visual import VisualResult

CITATION = "CGA C-13"

LOSS_LIMIT_SHARE = Fraction(1, 100)
GAIN_LIMIT_HUNDREDTHS = 25


@dataclass(frozen=True)
class AcetyleneOutcome:
    """What the examination decided, and how it decided it."""

    verdict: Verdict
    result: VisualResult
    reasons: tuple[str, ...]
    loss_hundredths: int

    @property
    def passed(self) -> bool:
        return self.verdict is Verdict.PASS and self.result is VisualResult.PASS

    def describe(self) -> str:
        line = f"{self.result.value}"
        if self.reasons:
            line = f"{line}: " + "; ".join(self.reasons)
        return line


def marked_tare(cylinder: Cylinder) -> int:
    if cylinder.specification.family is not SpecFamily.ACETYLENE:
        raise RuleViolationError(f"{cylinder.specification} is not an acetylene cylinder", CITATION)
    if cylinder.tare_hundredths_lb is None:
        raise RuleViolationError(
            f"{cylinder.key} carries no marked tare weight, so nothing can be weighed against it",
            CITATION,
        )
    return cylinder.tare_hundredths_lb


def loss_limit(cylinder: Cylinder) -> int:
    """The most weight a cylinder may have lost, in hundredths of a pound."""
    marked = Fraction(marked_tare(cylinder)) * LOSS_LIMIT_SHARE
    return (marked.numerator * 2 + marked.denominator) // (marked.denominator * 2)


def evaluate(cylinder: Cylinder, exam: AcetyleneExam) -> AcetyleneOutcome:
    """Judge one acetylene examination."""
    marked = marked_tare(cylinder)
    loss = exam.loss_against(marked)
    limit = loss_limit(cylinder)

    condemning: list[str] = []
    repairs: list[str] = []

    if loss > limit:
        condemning.append(
            f"lost {loss / 100:.2f} lb against its marked tare, past the "
            f"{limit / 100:.2f} lb the mass may lose"
        )
    if -loss > GAIN_LIMIT_HUNDREDTHS:
        condemning.append(
            f"weighs {-loss / 100:.2f} lb over its marked tare, which is water in the mass"
        )
    if exam.mass_settled:
        condemning.append("the porous mass has settled and left a void")
    if not exam.shell_sound:
        condemning.append("the shell is unsound")
    if not exam.fuse_plugs_sound:
        repairs.append("the fusible plugs have to be replaced")
    if not exam.cap_sound:
        repairs.append("the cap has to be replaced")

    if condemning:
        return AcetyleneOutcome(Verdict.CONDEMN, VisualResult.CONDEMN, tuple(condemning), loss)
    if repairs:
        return AcetyleneOutcome(Verdict.PASS, VisualResult.REPAIR, tuple(repairs), loss)
    return AcetyleneOutcome(Verdict.PASS, VisualResult.PASS, (), loss)
