"""The fleet and the work, cut by what is in the cylinders.

The gas is the cut that answers the shop's commercial questions. Oxygen and
inert cylinders come back on a five year cycle and pay the rent; acetylene
cylinders take a tenth of the work and a third of the arguments; the corrosive
services are where the condemnations are. None of that shows in a report
organised by month.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.model.cylinder import CylinderStatus
from starstamp.model.event import Outcome
from starstamp.model.service import GasService, all_services
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.fills import FillRepository
from starstamp.text.table import render_table


@dataclass(frozen=True)
class GasRow:
    """One gas, and what the shop does with it."""

    service: GasService
    on_the_books: int
    tested: int
    condemned: int
    filled: int

    @property
    def condemn_rate(self) -> Fraction:
        if self.tested == 0:
            return Fraction(0)
        return Fraction(self.condemned, self.tested) * 100

    @property
    def is_idle(self) -> bool:
        return self.on_the_books == 0 and self.tested == 0

    def row(self) -> list[str]:
        return [
            self.service.code,
            self.service.name,
            str(self.on_the_books),
            str(self.tested),
            str(self.condemned),
            f"{float(self.condemn_rate):.1f}%",
            str(self.filled),
        ]


@dataclass(frozen=True)
class GasReport:
    """Every gas the shop has anything to do with."""

    first: date
    last: date
    rows: tuple[GasRow, ...]

    @property
    def busy(self) -> tuple[GasRow, ...]:
        return tuple(row for row in self.rows if not row.is_idle)

    def worst(self) -> GasRow | None:
        tested = [row for row in self.rows if row.tested >= 5]
        if not tested:
            return None
        return max(tested, key=lambda row: row.condemn_rate)

    def describe(self) -> str:
        if not self.busy:
            return "the shop holds nothing and has done nothing"
        gases = len(self.busy)
        cylinders = sum(row.on_the_books for row in self.rows)
        worst = self.worst()
        line = f"{cylinders} cylinders across {gases} gases"
        if worst is not None:
            line = f"{line}; {worst.service} condemns worst at {float(worst.condemn_rate):.1f}%"
        return line


def build(book: Book, first: date, last: date) -> GasReport:
    cylinders = CylinderRepository(book.connection)
    events = EventRepository(book.connection)
    fills = FillRepository(book.connection)

    holdings: dict[str, int] = {}
    for status in (CylinderStatus.IN_SERVICE, CylinderStatus.IN_SHOP):
        for cylinder in cylinders.with_status(status):
            holdings[cylinder.service.code] = holdings.get(cylinder.service.code, 0) + 1

    tested: dict[str, int] = {}
    condemned: dict[str, int] = {}
    for event in events.between(first, last):
        if not event.state.stands:
            continue
        code = cylinders.by_key(event.cylinder).service.code
        tested[code] = tested.get(code, 0) + 1
        if event.outcome is Outcome.CONDEMN:
            condemned[code] = condemned.get(code, 0) + 1

    filled: dict[str, int] = {}
    for fill in fills.between(first, last):
        filled[fill.service.code] = filled.get(fill.service.code, 0) + 1

    rows = tuple(
        GasRow(
            service=service,
            on_the_books=holdings.get(service.code, 0),
            tested=tested.get(service.code, 0),
            condemned=condemned.get(service.code, 0),
            filled=filled.get(service.code, 0),
        )
        for service in all_services()
    )
    return GasReport(first, last, rows)


def render(report: GasReport) -> str:
    if not report.busy:
        return report.describe()
    table = render_table(
        ["code", "gas", "held", "tested", "condemned", "rate", "filled"],
        [row.row() for row in report.busy],
        right=(2, 3, 4, 5, 6),
    )
    return f"{table}\n\n{report.describe()}"
