"""Judging an ultrasonic examination.

The criterion is the cylinder's minimum design wall, which is a share of the
nominal wall its maker built it to rather than a number anybody measures. So
an ultrasonic examination cannot be judged at all on a cylinder whose wall the
book does not carry, and the refusal for that is deliberately different from a
condemnation: one means the shop cannot say, and the other means the cylinder
is finished.

The exam also has to be an exam. Six points across three bands is the floor,
because a scan that only looked at the mid barrel will pass a cylinder that is
thin at the base every time.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import Cylinder
from starstamp.model.specification import SpecFamily
from starstamp.model.ultrasonic import MINIMUM_POINTS, Scan
from starstamp.rules.pressure_test import Verdict

CITATION = "49 CFR 180.209(g)"

DESIGN_MINIMUM_SHARE = Fraction(9, 10)
MINIMUM_BANDS = 3
WATCH_MARGIN = Fraction(1, 50)


@dataclass(frozen=True)
class ScanOutcome:
    """The verdict on a scan, and anything worth watching."""

    verdict: Verdict
    reasons: tuple[str, ...]
    watch: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.verdict is Verdict.PASS

    def describe(self) -> str:
        line = self.verdict.value
        if self.reasons:
            line = f"{line}: " + "; ".join(self.reasons)
        if self.watch:
            line = f"{line} (watch: " + "; ".join(self.watch) + ")"
        return line


def design_minimum(cylinder: Cylinder) -> int:
    """The thinnest the wall may be anywhere, in thousandths."""
    nominal = cylinder.require_wall()
    exact = Fraction(nominal) * DESIGN_MINIMUM_SHARE
    return (exact.numerator * 2 + exact.denominator) // (exact.denominator * 2)


def check_scan_is_an_examination(scan: Scan) -> None:
    """Refuse a scan too thin to mean anything, before judging it."""
    if scan.count < MINIMUM_POINTS:
        raise RuleViolationError(
            f"an ultrasonic examination takes at least {MINIMUM_POINTS} points, "
            f"and this one has {scan.count}",
            CITATION,
        )
    if len(scan.bands) < MINIMUM_BANDS:
        raise RuleViolationError(
            f"the points have to cover at least {MINIMUM_BANDS} bands, "
            f"and these cover {len(scan.bands)}",
            CITATION,
        )


def evaluate(cylinder: Cylinder, scan: Scan) -> ScanOutcome:
    """Judge one examination against the cylinder's own design minimum."""
    if cylinder.specification.family is not SpecFamily.SEAMLESS_ALUMINUM:
        raise RuleViolationError(
            f"{cylinder.specification} is not examined ultrasonically here", CITATION
        )
    check_scan_is_an_examination(scan)
    floor = design_minimum(cylinder)
    thin = scan.below(floor)
    if thin:
        return ScanOutcome(
            Verdict.CONDEMN,
            tuple(
                f"{reading} is under the {floor / 1000:.3f} in design minimum" for reading in thin
            ),
        )
    ceiling = Fraction(floor) * (1 + WATCH_MARGIN)
    watch = tuple(
        f"{reading} is within two percent of the design minimum"
        for reading in scan.readings
        if Fraction(reading.thousandths_in) <= ceiling
    )
    return ScanOutcome(Verdict.PASS, (), watch)
