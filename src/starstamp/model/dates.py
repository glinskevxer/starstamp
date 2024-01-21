"""Dates as the shop writes them.

Two calendars meet here. Requalification marks carry a month and a year and
nothing finer, because that is all there is room to stamp into the shoulder of
a cylinder. Everything else the shop does happens on a particular day. Mixing
the two is how a cylinder gets filled a month after it went out of test, so
they are separate types.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

from starstamp.errors import ValidationError

_ISO = re.compile(r"^(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})$")
_STAMP = re.compile(r"^(?P<m>\d{1,2})\s*[-/ ]\s*(?P<y>\d{2}|\d{4})$")


def parse_day(text: str) -> date:
    """Parse an ISO day. The shop's paperwork uses nothing else."""
    match = _ISO.match(text.strip())
    if match is None:
        raise ValidationError(f"date must be YYYY-MM-DD, got {text!r}")
    try:
        return date(int(match.group("y")), int(match.group("m")), int(match.group("d")))
    except ValueError as exc:
        raise ValidationError(f"no such date: {text!r}") from exc


@dataclass(frozen=True, order=True)
class StampedMonth:
    """A month and year, the way a requalification mark is stamped."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValidationError(f"month must be 1 through 12, got {self.month}")
        if not 1900 <= self.year <= 2199:
            raise ValidationError(f"year is outside anything a cylinder carries: {self.year}")

    @classmethod
    def parse(cls, text: str) -> StampedMonth:
        """Read the stamped forms: 7-24, 07/24, 07-2024, 7 2024."""
        match = _STAMP.match(text.strip())
        if match is None:
            raise ValidationError(f"stamped month must be M-YY or MM-YYYY, got {text!r}")
        year = int(match.group("y"))
        if year < 100:
            # A two digit stamp is read into the window the shop actually sees.
            year += 2000 if year <= 79 else 1900
        return cls(year, int(match.group("m")))

    @classmethod
    def of(cls, day: date) -> StampedMonth:
        return cls(day.year, day.month)

    def first_day(self) -> date:
        return date(self.year, self.month, 1)

    def last_day(self) -> date:
        return date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])

    def plus_years(self, years: int) -> StampedMonth:
        if years < 0:
            raise ValidationError(f"a requalification interval is never negative: {years}")
        return StampedMonth(self.year + years, self.month)

    def plus_months(self, months: int) -> StampedMonth:
        total = (self.year * 12 + self.month - 1) + months
        return StampedMonth(total // 12, total % 12 + 1)

    def months_until(self, other: StampedMonth) -> int:
        return (other.year * 12 + other.month) - (self.year * 12 + self.month)

    def contains(self, day: date) -> bool:
        return day.year == self.year and day.month == self.month

    def __str__(self) -> str:
        return f"{self.month:02d}-{self.year % 100:02d}"

    def long_form(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"
