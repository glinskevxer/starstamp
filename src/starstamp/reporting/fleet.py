"""What one account's cylinders look like, taken together.

A distributor with four hundred cylinders does not care about any one of them.
They care how many fall due next quarter, how many the shop has condemned this
year, and whether the ones they keep sending back are the same ones. This
report answers those, and it is the one that gets printed and posted.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.model.cylinder import Cylinder, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.event import Outcome
from starstamp.service.fill import DueRow, FillService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.text.table import render_table


@dataclass(frozen=True)
class FleetStanding:
    """One account's cylinders as of a day."""

    owner_code: str
    day: date
    rows: tuple[DueRow, ...]
    condemned_this_year: int
    condemned_ever: int

    @property
    def size(self) -> int:
        return len(self.rows)

    def by_status(self) -> dict[str, int]:
        counter: Counter[str] = Counter(row.cylinder.status.value for row in self.rows)
        return dict(sorted(counter.items()))

    def by_service(self) -> dict[str, int]:
        counter: Counter[str] = Counter(row.cylinder.service.code for row in self.rows)
        return dict(sorted(counter.items()))

    def never_tested(self) -> tuple[DueRow, ...]:
        return tuple(row for row in self.rows if row.never_tested)

    def overdue(self) -> tuple[DueRow, ...]:
        return tuple(row for row in self.rows if row.overdue)

    def due_within(self, months: int) -> tuple[DueRow, ...]:
        return tuple(
            row
            for row in self.rows
            if row.months_left is not None and 0 <= row.months_left <= months
        )

    def due_by_month(self) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for row in self.rows:
            if row.due is not None:
                counter[row.due.long_form()] += 1
        return dict(sorted(counter.items()))

    def condemn_rate(self) -> Fraction:
        """Condemnations as a share of the cylinders the account has ever had."""
        denominator = self.size + self.condemned_ever
        if denominator == 0:
            return Fraction(0)
        return Fraction(self.condemned_ever, denominator) * 100

    def describe(self) -> str:
        lines = [
            f"{self.owner_code} holds {self.size} cylinders on {self.day.isoformat()}",
            "  " + ", ".join(f"{count} {status}" for status, count in self.by_status().items()),
            "  " + ", ".join(f"{count} {code}" for code, count in self.by_service().items()),
        ]
        overdue = self.overdue()
        if overdue:
            lines.append(f"  {len(overdue)} out of test")
        untested = self.never_tested()
        if untested:
            lines.append(f"  {len(untested)} never requalified here")
        lines.append(
            f"  {self.condemned_this_year} condemned this year, {self.condemned_ever} in all, "
            f"{float(self.condemn_rate()):.1f}% of everything seen"
        )
        return "\n".join(lines)


def build(book: Book, owner_code: str, day: date) -> FleetStanding:
    cylinders = CylinderRepository(book.connection)
    events = EventRepository(book.connection)
    fill = FillService(book)
    fleet: list[Cylinder] = cylinders.for_owner(owner_code.upper())
    rows = tuple(fill.due_row(cylinder, day) for cylinder in fleet)

    year = StampedMonth(day.year, 1).first_day()
    condemned_ever = 0
    condemned_this_year = 0
    for cylinder in fleet:
        for event in events.for_cylinder(cylinder.key, standing_only=True):
            if event.outcome is Outcome.CONDEMN:
                condemned_ever += 1
                if event.performed_on >= year:
                    condemned_this_year += 1
    return FleetStanding(
        owner_code=owner_code.upper(),
        day=day,
        rows=rows,
        condemned_this_year=condemned_this_year,
        condemned_ever=condemned_ever,
    )


def render(standing: FleetStanding, *, months: int = 6) -> str:
    lines = [standing.describe()]
    coming = standing.due_within(months) + standing.overdue()
    if coming:
        lines.append("")
        lines.append(
            render_table(
                ["cylinder", "service", "status", "due", "months"],
                [
                    [
                        str(row.cylinder.key),
                        row.cylinder.service.code,
                        row.cylinder.status.value,
                        "-" if row.due is None else str(row.due),
                        "-" if row.months_left is None else str(row.months_left),
                    ]
                    for row in sorted(coming, key=lambda item: item.months_left or 0)
                ],
                right=(4,),
            )
        )
    profile = standing.due_by_month()
    if profile:
        lines.append("")
        lines.append(
            render_table(
                ["due month", "cylinders"],
                [[month, str(count)] for month, count in profile.items()],
                right=(1,),
            )
        )
    return "\n".join(lines)


def in_shop(book: Book, owner_code: str) -> list[Cylinder]:
    return [
        cylinder
        for cylinder in CylinderRepository(book.connection).for_owner(owner_code.upper())
        if cylinder.status in {CylinderStatus.IN_SHOP, CylinderStatus.AWAITING_REPAIR}
    ]
