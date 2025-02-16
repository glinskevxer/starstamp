"""Judging a fill after the fact.

The rule that matters is not the gauge reading. It is the pressure the
cylinder will sit at once it has cooled to seventy, because that is the number
the service pressure marking is about. A cylinder filled to 2500 psi at 110
degrees is inside its marking; the same reading at 40 degrees is an overfill,
and the two are indistinguishable without the temperature.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from starstamp.model.cylinder import Cylinder
from starstamp.model.fillrecord import FillRecord
from starstamp.model.units import Pressure
from starstamp.rules.fill import PLUS_OVERFILL

CITATION = "49 CFR 173.301(a)"

TOLERANCE = Fraction(1, 100)


class FillVerdict(Enum):
    """What the fill log says about one fill."""

    WITHIN = "within"
    OVERFILLED = "overfilled"
    UNDERFILLED = "underfilled"

    @property
    def is_a_problem(self) -> bool:
        return self is FillVerdict.OVERFILLED


@dataclass(frozen=True)
class FillJudgement:
    """The verdict, and the numbers it came from."""

    verdict: FillVerdict
    settled: Pressure | None
    ceiling: Pressure | None
    reasons: tuple[str, ...] = ()

    @property
    def is_within(self) -> bool:
        return self.verdict is FillVerdict.WITHIN

    def describe(self) -> str:
        if not self.reasons:
            return self.verdict.value
        return f"{self.verdict.value}: " + "; ".join(self.reasons)


def ceiling_for(cylinder: Cylinder, *, plus: bool) -> Pressure | None:
    """The most a cylinder may settle at, given whether it wears a plus."""
    marked = cylinder.specification.service_pressure
    if marked is None:
        return None
    if plus:
        return marked.scaled(PLUS_OVERFILL)
    return marked


def judge(cylinder: Cylinder, record: FillRecord, *, plus: bool = False) -> FillJudgement:
    """Judge one fill against what the cylinder is marked for."""
    if record.is_by_weight:
        return FillJudgement(FillVerdict.WITHIN, None, None)
    ceiling = ceiling_for(cylinder, plus=plus)
    settled = record.settled_pressure()
    if ceiling is None:
        return FillJudgement(
            FillVerdict.WITHIN,
            settled,
            None,
            ("the cylinder carries no service pressure to judge against",),
        )
    allowance = Fraction(ceiling.psig) * TOLERANCE
    if Fraction(settled.psig) > Fraction(ceiling.psig) + allowance:
        return FillJudgement(
            FillVerdict.OVERFILLED,
            settled,
            ceiling,
            (
                f"settles at {settled} against a ceiling of {ceiling}"
                + (" with the plus rating" if plus else ""),
            ),
        )
    half = Fraction(ceiling.psig, 2)
    if Fraction(settled.psig) < half:
        return FillJudgement(
            FillVerdict.UNDERFILLED,
            settled,
            ceiling,
            (f"settles at {settled}, under half of {ceiling}",),
        )
    return FillJudgement(FillVerdict.WITHIN, settled, ceiling)
