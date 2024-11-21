"""What the shop condemns, and what the cylinders had in common.

The useful question is not how many were condemned. It is whether they were
the same age, the same specification or the same customer's, because all three
of those point at something the shop can tell somebody about. A distributor
whose cylinders fail at nineteen years is buying badly used cylinders; one
whose fail at four is storing them wet.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.model.cylinder import Cylinder
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.text.table import render_table


@dataclass(frozen=True)
class Condemned:
    """One condemnation, with the cylinder it happened to."""

    cylinder: Cylinder
    event: RequalificationEvent

    @property
    def age_years(self) -> int:
        """How old the cylinder was when it was condemned, in whole years."""
        months = self.cylinder.manufactured.months_until(self.event.marked_month)
        return months // 12

    @property
    def cause(self) -> str:
        if not self.event.reasons:
            return "no reason recorded"
        return self.event.reasons[0].split(",")[0]

    def row(self) -> list[str]:
        return [
            str(self.cylinder.key),
            self.cylinder.owner_code,
            str(self.cylinder.specification),
            self.cylinder.manufactured.long_form(),
            self.event.performed_on.isoformat(),
            str(self.age_years),
            self.cause,
        ]


@dataclass(frozen=True)
class Analysis:
    """Every condemnation in a window, grouped the ways that pay."""

    first: date
    last: date
    condemnations: tuple[Condemned, ...]

    @property
    def count(self) -> int:
        return len(self.condemnations)

    def by_cause(self) -> dict[str, int]:
        counter: Counter[str] = Counter(item.cause for item in self.condemnations)
        return dict(sorted(counter.items(), key=lambda pair: (-pair[1], pair[0])))

    def by_specification(self) -> dict[str, int]:
        counter: Counter[str] = Counter(
            str(item.cylinder.specification) for item in self.condemnations
        )
        return dict(sorted(counter.items()))

    def by_owner(self) -> dict[str, int]:
        counter: Counter[str] = Counter(item.cylinder.owner_code for item in self.condemnations)
        return dict(sorted(counter.items(), key=lambda pair: (-pair[1], pair[0])))

    def by_decade(self) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for item in self.condemnations:
            decade = (item.cylinder.manufactured.year // 10) * 10
            counter[f"{decade}s"] += 1
        return dict(sorted(counter.items()))

    def average_age(self) -> Fraction:
        if not self.condemnations:
            return Fraction(0)
        return Fraction(sum(item.age_years for item in self.condemnations), len(self.condemnations))

    def oldest(self) -> Condemned | None:
        if not self.condemnations:
            return None
        return max(self.condemnations, key=lambda item: item.age_years)

    def describe(self) -> str:
        if not self.condemnations:
            return f"nothing condemned between {self.first} and {self.last}"
        lines = [
            f"{self.count} condemned between {self.first} and {self.last}, "
            f"average age {float(self.average_age()):.1f} years"
        ]
        for cause, count in self.by_cause().items():
            lines.append(f"  {count} x {cause}")
        return "\n".join(lines)


def build(book: Book, first: date, last: date) -> Analysis:
    events = EventRepository(book.connection)
    cylinders = CylinderRepository(book.connection)
    found: list[Condemned] = []
    for event in events.between(first, last):
        if event.outcome is not Outcome.CONDEMN or not event.state.stands:
            continue
        found.append(Condemned(cylinders.by_key(event.cylinder), event))
    return Analysis(first, last, tuple(found))


def render(analysis: Analysis) -> str:
    lines = [analysis.describe()]
    if not analysis.condemnations:
        return lines[0]
    lines.append("")
    lines.append(
        render_table(
            ["cylinder", "owner", "spec", "made", "condemned", "age", "cause"],
            [item.row() for item in analysis.condemnations],
            right=(5,),
        )
    )
    for heading, grouped in (
        ("specification", analysis.by_specification()),
        ("owner", analysis.by_owner()),
        ("made", analysis.by_decade()),
    ):
        lines.append("")
        lines.append(
            render_table(
                [heading, "condemned"],
                [[key, str(value)] for key, value in grouped.items()],
                right=(1,),
            )
        )
    return "\n".join(lines)
