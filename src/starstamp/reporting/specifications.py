"""The fleet by specification, with what the shop can actually do to each.

Two shops with the same number of cylinders can have entirely different work
in front of them, because the specification decides the interval, the method
and half the refusals. This report puts the fleet next to what the shop is
approved and equipped to do, which is the question behind "should we buy an
ultrasonic unit".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import ConflictError
from starstamp.model.cylinder import Cylinder, CylinderStatus
from starstamp.model.facility import Facility
from starstamp.model.method import Method
from starstamp.rules.method_matrix import permitted_methods
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.facility import FacilityRepository
from starstamp.text.table import render_table


@dataclass(frozen=True)
class SpecRow:
    """One specification, and what the shop may do to it."""

    marking: str
    cylinders: int
    oldest_year: int
    methods: frozenset[Method]
    covered: frozenset[Method]

    @property
    def is_covered(self) -> bool:
        return bool(self.covered)

    @property
    def missing(self) -> frozenset[Method]:
        return self.methods - self.covered

    def row(self) -> list[str]:
        return [
            self.marking,
            str(self.cylinders),
            str(self.oldest_year),
            ", ".join(sorted(item.label for item in self.methods)) or "-",
            ", ".join(sorted(item.label for item in self.covered)) or "none",
        ]


@dataclass(frozen=True)
class SpecReport:
    """Every specification on the books."""

    day: date
    rows: tuple[SpecRow, ...]

    @property
    def uncovered(self) -> tuple[SpecRow, ...]:
        return tuple(row for row in self.rows if not row.is_covered)

    def describe(self) -> str:
        if not self.rows:
            return "nothing on the books"
        cylinders = sum(row.cylinders for row in self.rows)
        line = f"{cylinders} cylinders across {len(self.rows)} specifications"
        if self.uncovered:
            names = ", ".join(row.marking for row in self.uncovered)
            line = f"{line}; nothing the shop holds covers {names}"
        return line


def build(book: Book, day: date) -> SpecReport:
    cylinders = CylinderRepository(book.connection)
    facilities = FacilityRepository(book.connection)
    facility: Facility | None
    try:
        facility = facilities.only()
    except ConflictError:
        # A book with no shop recorded still lists its fleet; it just cannot
        # say what the shop is approved for.
        facility = None

    grouped: dict[str, list[Cylinder]] = {}
    for status in (CylinderStatus.IN_SERVICE, CylinderStatus.IN_SHOP):
        for cylinder in cylinders.with_status(status):
            grouped.setdefault(str(cylinder.specification), []).append(cylinder)

    rows: list[SpecRow] = []
    for marking, found in sorted(grouped.items()):
        first = found[0]
        methods = permitted_methods(first.specification, first.service)
        covered = (
            frozenset(
                method
                for method in methods
                if facility is not None and facility.may_perform(method, day)
            )
            if facility is not None
            else frozenset()
        )
        rows.append(
            SpecRow(
                marking=marking,
                cylinders=len(found),
                oldest_year=min(item.manufactured.year for item in found),
                methods=methods,
                covered=covered,
            )
        )
    return SpecReport(day, tuple(rows))


def render(report: SpecReport) -> str:
    if not report.rows:
        return report.describe()
    table = render_table(
        ["specification", "cylinders", "oldest", "takes", "we can do"],
        [row.row() for row in report.rows],
        right=(1, 2),
    )
    return f"{table}\n\n{report.describe()}"
