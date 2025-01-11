"""Working out which days a command means.

Four commands had grown their own copy of this and two of them defaulted
differently, so a throughput report and an invoice draft run on the same day
covered different windows. There is one rule now: a named month wins, an
explicit pair of days comes next, and the fallback is the month the shop's
today falls in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import ValidationError
from starstamp.model.dates import StampedMonth, parse_day


@dataclass(frozen=True)
class Window:
    """A closed range of days, first and last both included."""

    first: date
    last: date

    def __post_init__(self) -> None:
        if self.last < self.first:
            raise ValidationError(f"a window ends after it starts, got {self.first} to {self.last}")

    @property
    def days(self) -> int:
        return (self.last - self.first).days + 1

    def contains(self, day: date) -> bool:
        return self.first <= day <= self.last

    def __str__(self) -> str:
        return f"{self.first.isoformat()} to {self.last.isoformat()}"


def parse_month(text: str) -> StampedMonth:
    """Read YYYY-MM, which is how every command names a month."""
    year, separator, month = text.strip().partition("-")
    if not separator or not year.isdigit() or not month.isdigit():
        raise ValidationError(f"a month is YYYY-MM, got {text!r}")
    return StampedMonth(int(year), int(month))


def resolve(
    today: date,
    *,
    month: str | None = None,
    first: str | None = None,
    last: str | None = None,
) -> Window:
    """The window a command means, from whatever it was given."""
    if month is not None:
        stamped = parse_month(month)
        return Window(stamped.first_day(), stamped.last_day())
    if first is not None and last is not None:
        return Window(parse_day(first), parse_day(last))
    if first is not None:
        return Window(parse_day(first), today)
    if last is not None:
        stamped = StampedMonth.of(parse_day(last))
        return Window(stamped.first_day(), parse_day(last))
    stamped = StampedMonth.of(today)
    return Window(stamped.first_day(), stamped.last_day())
