"""The two marks a cylinder can earn beyond the date and the RIN.

A star gets stamped after the requalification date and means the cylinder is
on a ten year interval instead of five. A plus sign means it may be filled ten
percent over its marked service pressure. Neither is a reward for passing.
Both are conclusions drawn from readings the other rules already produced, and
both are refused the moment any one of their conditions is missing.

This is the part of the shop where the composition bites hardest. A star needs
an expansion reading, so it needs a method that takes one, so it needs a
specification that permits that method and a rig that was in calibration on
the day. Every one of those decisions was made somewhere else, and all this
module does is refuse to draw the conclusion when one of them went the other
way.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.model.cylinder import Cylinder
from starstamp.model.dates import StampedMonth
from starstamp.model.method import Method
from starstamp.model.specification import SpecFamily
from starstamp.model.testrecord import PressureReadings
from starstamp.rules.interval import is_out_of_test
from starstamp.rules.pressure_test import PressureOutcome
from starstamp.rules.visual import VisualAssessment, VisualResult

STAR_CITATION = "49 CFR 180.209(f)"
PLUS_CITATION = "49 CFR 173.302a(b)"

STAR_SPECS = frozenset({"3A", "3AA", "3AAX"})
PLUS_PERMANENT_LIMIT = Fraction(5)
PLUS_ELASTIC_MARGIN = Fraction(9, 10)


@dataclass(frozen=True)
class Eligibility:
    """Whether a mark may be stamped, and everything standing in the way."""

    mark: str
    citation: str
    refusals: tuple[str, ...]

    @property
    def granted(self) -> bool:
        return not self.refusals

    def describe(self) -> str:
        if self.granted:
            return f"{self.mark} granted"
        return f"{self.mark} refused: " + "; ".join(self.refusals)


def star_eligibility(
    cylinder: Cylinder,
    method: Method,
    readings: PressureReadings | None,
    pressure: PressureOutcome | None,
    visual: VisualAssessment,
    *,
    previous_due: StampedMonth | None,
    day: date,
) -> Eligibility:
    """Whether this requalification earns a star."""
    refusals: list[str] = []
    specification = cylinder.specification
    if specification.family is not SpecFamily.SEAMLESS_STEEL:
        refusals.append(f"{specification} is not seamless steel")
    elif specification.code not in STAR_SPECS:
        refusals.append(f"{specification.code} is outside the starred specifications")
    if not cylinder.service.is_dry_service:
        refusals.append(f"{cylinder.service} is not a dry service")
    if not cylinder.service.interval_eligible:
        refusals.append(f"{cylinder.service} runs on its own interval")
    if not method.measures_expansion:
        refusals.append(f"{method.label} takes no expansion reading")
    if pressure is None or not pressure.passed:
        refusals.append("the pressure test did not pass")
    if visual.result is not VisualResult.PASS:
        refusals.append(f"the visual inspection came back {visual.result.value}")
    if readings is None or not readings.has_expansion:
        refusals.append("there is no expansion reading to rest a star on")
    elif cylinder.rejection_elastic_expansion is None:
        refusals.append(f"{cylinder.key} carries no marked rejection elastic expansion")
    elif readings.elastic > cylinder.rejection_elastic_expansion:
        refusals.append("the elastic expansion is past the marked limit")
    if previous_due is not None and is_out_of_test(previous_due, day):
        refusals.append(f"the cylinder was out of test from {previous_due.long_form()}")
    return Eligibility("star", STAR_CITATION, tuple(refusals))


def plus_eligibility(
    cylinder: Cylinder,
    method: Method,
    readings: PressureReadings | None,
    pressure: PressureOutcome | None,
    visual: VisualAssessment,
) -> Eligibility:
    """Whether this requalification earns the plus rating.

    The plus is the tighter of the two. It is not enough to stay inside the
    ten percent that keeps a cylinder alive; the cylinder has to keep under
    five, and its elastic expansion has to sit clear of the marked limit
    rather than merely under it.
    """
    refusals: list[str] = []
    specification = cylinder.specification
    if specification.code not in STAR_SPECS:
        refusals.append(f"{specification.code} does not take a plus rating")
    if method is not Method.VOLUMETRIC:
        refusals.append(f"a plus rating rests on a water jacket test, not {method.label}")
    if not cylinder.service.is_dry_service:
        refusals.append(f"{cylinder.service} is not a dry service")
    if pressure is None or not pressure.passed:
        refusals.append("the pressure test did not pass")
    if visual.result is not VisualResult.PASS:
        refusals.append(f"the visual inspection came back {visual.result.value}")
    if readings is None or not readings.has_expansion:
        refusals.append("there is no expansion reading to rest a plus on")
    else:
        if readings.permanent_percentage > PLUS_PERMANENT_LIMIT:
            refusals.append(
                f"it kept {float(readings.permanent_percentage):.2f}% of its expansion, "
                f"past the {float(PLUS_PERMANENT_LIMIT):.0f}% a plus allows"
            )
        marked = cylinder.rejection_elastic_expansion
        if marked is None:
            refusals.append(f"{cylinder.key} carries no marked rejection elastic expansion")
        else:
            ceiling = Fraction(marked.tenths_cc) * PLUS_ELASTIC_MARGIN
            if Fraction(readings.elastic.tenths_cc) > ceiling:
                refusals.append("the elastic expansion is inside a tenth of the marked limit")
    return Eligibility("plus", PLUS_CITATION, tuple(refusals))
