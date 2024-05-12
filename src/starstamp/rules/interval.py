"""How long a requalification is good for, and when the next one falls due.

The interval is not a property of the cylinder. It is decided by the cylinder,
the gas, and the method that was actually used, and the last of those is the
one shops get wrong. A propane cylinder given an external visual is good for
five years; the same cylinder given a volumetric test on the same day is good
for twelve. Reading the interval off the specification alone puts seven years
on a cylinder that has not earned them.

A star is the other lever. It is not recorded here, only consumed: the star
rules decide whether one may be stamped, and this module turns that answer
into a due date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import Cylinder
from starstamp.model.dates import StampedMonth
from starstamp.model.method import Method
from starstamp.model.specification import SpecFamily

CITATION = "49 CFR 180.209"

STANDARD_YEARS = 5
STARRED_YEARS = 10
HIGH_STRENGTH_YEARS = 3
ACETYLENE_YEARS = 10
DEDICATED_VOLUMETRIC_YEARS = 12
HIGH_STRENGTH_LIFE_YEARS = 24


@dataclass(frozen=True)
class Interval:
    """An interval and the reason it is the length it is."""

    years: int
    reason: str

    def due_after(self, marked: StampedMonth) -> StampedMonth:
        """A requalification lasts to the end of the month it expires in."""
        return marked.plus_years(self.years)

    def __str__(self) -> str:
        return f"{self.years} years ({self.reason})"


def life_limit(cylinder: Cylinder) -> StampedMonth | None:
    """The month past which the cylinder cannot be requalified at all.

    Only high strength steel carries one. Everything else here lives as long
    as it keeps passing.
    """
    if cylinder.specification.family is SpecFamily.HIGH_STRENGTH_STEEL:
        return cylinder.manufactured.plus_years(HIGH_STRENGTH_LIFE_YEARS)
    return None


def life_expired(cylinder: Cylinder, day: date) -> bool:
    limit = life_limit(cylinder)
    if limit is None:
        return False
    return day > limit.last_day()


def interval_for(cylinder: Cylinder, method: Method, *, starred: bool = False) -> Interval:
    """The interval this cylinder earns from this method today."""
    family = cylinder.specification.family
    if life_expired(cylinder, cylinder.manufactured.first_day()):
        raise RuleViolationError(f"{cylinder.key} is past its service life", CITATION)

    if starred and not method.measures_expansion:
        raise RuleViolationError(
            f"a star rests on an expansion reading, and {method.label} takes none", CITATION
        )

    if family is SpecFamily.ACETYLENE:
        if starred:
            raise RuleViolationError("an acetylene cylinder is never starred", CITATION)
        return Interval(ACETYLENE_YEARS, "acetylene cylinders run on a ten year visual")

    if family is SpecFamily.HIGH_STRENGTH_STEEL:
        if starred:
            raise RuleViolationError("high strength steel is never starred", CITATION)
        return Interval(HIGH_STRENGTH_YEARS, "high strength steel is requalified every three")

    if family is SpecFamily.WELDED_STEEL and cylinder.service.requires_dedicated_cylinder:
        if method is Method.EXTERNAL_VISUAL:
            return Interval(STANDARD_YEARS, "external visual in a dedicated service")
        if method is Method.VOLUMETRIC:
            return Interval(DEDICATED_VOLUMETRIC_YEARS, "volumetric test in a dedicated service")

    if starred:
        return Interval(STARRED_YEARS, "starred")
    return Interval(STANDARD_YEARS, "the standard interval")


def due_month(
    cylinder: Cylinder, marked: StampedMonth, method: Method, *, starred: bool = False
) -> StampedMonth:
    """The month the next requalification falls due in."""
    return interval_for(cylinder, method, starred=starred).due_after(marked)


def is_out_of_test(due: StampedMonth, day: date) -> bool:
    """A cylinder is in test through the last day of the month it expires in."""
    return day > due.last_day()


def months_remaining(due: StampedMonth, day: date) -> int:
    """Whole months from the day to the end of the due month, negative once past."""
    return StampedMonth.of(day).months_until(due)
