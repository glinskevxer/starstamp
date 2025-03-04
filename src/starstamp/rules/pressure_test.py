"""The criteria a cylinder is held to on the rig.

Which criteria apply is decided by the method, and the method was decided by
the specification. A proof pressure test is judged on whether the cylinder
leaked or took a set; a volumetric test is judged on two numbers and the
cylinder's own marked limit. Neither set of criteria means anything applied to
the other kind of test, and the shop that applies the ten percent rule to a
proof test will pass every one of them.

The rejection elastic expansion is the clearest case. It is stamped on the
cylinder by its maker, it is the largest elastic expansion the cylinder may
show and still be sound, and it is a criterion only when the method actually
measures elastic expansion. A welded cylinder carries no REE at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import Cylinder
from starstamp.model.method import Method
from starstamp.model.specification import SpecFamily
from starstamp.model.testrecord import MINIMUM_HOLD_SECONDS, PressureReadings
from starstamp.rules.method_matrix import required_test_pressure

CITATION = "49 CFR 180.205(i)"

PERMANENT_LIMIT_PERCENT = Fraction(10)
HIGH_STRENGTH_LIMIT_PERCENT = Fraction(5)
OVERPRESSURE_TOLERANCE = Fraction(11, 10)


class Verdict(Enum):
    """What the rig says about the cylinder."""

    PASS = "pass"
    CONDEMN = "condemn"


@dataclass(frozen=True)
class PressureOutcome:
    """The verdict and every criterion that produced it."""

    verdict: Verdict
    reasons: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.verdict is Verdict.PASS

    def describe(self) -> str:
        if not self.reasons:
            return self.verdict.value
        return f"{self.verdict.value}: " + "; ".join(self.reasons)


def permanent_limit(cylinder: Cylinder) -> Fraction:
    """The share of total expansion a cylinder may keep and still pass.

    High strength steel is held to half what everything else is, which is the
    reason 3HT cylinders come out of service so much sooner than 3AA.
    """
    if cylinder.specification.family is SpecFamily.HIGH_STRENGTH_STEEL:
        return HIGH_STRENGTH_LIMIT_PERCENT
    return PERMANENT_LIMIT_PERCENT


def check_pressure_reached(cylinder: Cylinder, readings: PressureReadings) -> None:
    """The rig has to have got to test pressure, and not far past it."""
    required = required_test_pressure(cylinder.specification)
    if readings.applied < required:
        raise RuleViolationError(
            f"{cylinder.key} was taken to {readings.applied}, short of the required {required}",
            CITATION,
        )
    ceiling = required.scaled(OVERPRESSURE_TOLERANCE)
    if readings.applied > ceiling:
        raise RuleViolationError(
            f"{cylinder.key} was taken to {readings.applied}, past the {ceiling} the rig may "
            "apply, so the cylinder is out of test rather than tested",
            CITATION,
        )


def evaluate(
    cylinder: Cylinder,
    method: Method,
    readings: PressureReadings,
    *,
    minimum_hold_seconds: int = MINIMUM_HOLD_SECONDS,
) -> PressureOutcome:
    """Judge one pressure test.

    A refusal here means the test was not performed properly and there is no
    verdict to record. A condemning outcome means the test was performed and
    the cylinder failed it. The two are not interchangeable: the first is
    repeated, the second ends the cylinder.
    """
    readings.require_for(method)
    if readings.hold_seconds < minimum_hold_seconds:
        raise RuleViolationError(
            f"{cylinder.key} was held {readings.hold_seconds}s, short of the "
            f"{minimum_hold_seconds}s the test calls for",
            CITATION,
        )
    check_pressure_reached(cylinder, readings)

    reasons: list[str] = []
    if readings.leaked:
        reasons.append("leaked under pressure")
    if readings.distorted:
        reasons.append("visibly distorted under pressure")

    if method.measures_expansion:
        limit = permanent_limit(cylinder)
        percentage = readings.permanent_percentage
        if percentage > limit:
            reasons.append(
                f"kept {float(percentage):.2f}% of its expansion, past the "
                f"{float(limit):.0f}% limit"
            )
        if cylinder.carries_ree and cylinder.rejection_elastic_expansion is not None:
            marked = cylinder.rejection_elastic_expansion
            if readings.elastic > marked:
                reasons.append(f"elastic expansion {readings.elastic} is past the marked {marked}")

    if reasons:
        return PressureOutcome(Verdict.CONDEMN, tuple(reasons))
    return PressureOutcome(Verdict.PASS, ())
