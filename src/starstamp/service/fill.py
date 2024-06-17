"""Answering the filling plant, and telling the shop what is coming due.

Both questions read the same two things: the cylinder as it stands and the
last requalification that still stands beside it. Neither recomputes a star.
The star was decided at the bench under conditions that no longer exist, and
guessing at it years later is how a cylinder gets filled five years past its
real due date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.cylinder import Cylinder, CylinderKey, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.service import GasService
from starstamp.rules.fill import FillDecision, decide
from starstamp.rules.interval import due_month, months_remaining
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository


@dataclass(frozen=True)
class DueRow:
    """One cylinder and when it next has to come back."""

    cylinder: Cylinder
    due: StampedMonth | None
    months_left: int | None
    last_pass: RequalificationEvent | None

    @property
    def never_tested(self) -> bool:
        return self.last_pass is None

    @property
    def overdue(self) -> bool:
        return self.months_left is not None and self.months_left < 0


class FillService:
    """What the plant and the front counter ask."""

    def __init__(self, book: Book) -> None:
        self.book = book
        self.cylinders = CylinderRepository(book.connection)
        self.events = EventRepository(book.connection)

    def decision(self, key: CylinderKey, gas: GasService, day: date) -> FillDecision:
        cylinder = self.cylinders.by_key(key)
        last_pass = self.events.latest_pass(key)
        starred = bool(last_pass and last_pass.starred)
        plus = bool(last_pass and last_pass.plus_rated)
        return decide(cylinder, gas, day, last_pass, starred=starred, plus=plus)

    def due_row(self, cylinder: Cylinder, day: date) -> DueRow:
        last_pass = self.events.latest_pass(cylinder.key)
        if last_pass is None or last_pass.outcome is not Outcome.PASS:
            return DueRow(cylinder, None, None, None)
        due = due_month(
            cylinder, last_pass.marked_month, last_pass.method, starred=last_pass.starred
        )
        return DueRow(cylinder, due, months_remaining(due, day), last_pass)

    def due_within(self, day: date, months: int, *, owner_code: str | None = None) -> list[DueRow]:
        """Everything falling due inside a window, soonest first.

        Cylinders that have never been requalified come back too, at the end,
        because they are the ones nobody is watching for.
        """
        if owner_code is not None:
            fleet = self.cylinders.for_owner(owner_code)
        else:
            fleet = [
                cylinder
                for status in (CylinderStatus.IN_SERVICE, CylinderStatus.IN_SHOP)
                for cylinder in self.cylinders.with_status(status)
            ]
        rows = [self.due_row(cylinder, day) for cylinder in fleet]
        inside = [row for row in rows if row.months_left is not None and row.months_left <= months]
        untested = [row for row in rows if row.never_tested]
        inside.sort(key=lambda row: (row.months_left or 0, str(row.cylinder.key)))
        return inside + untested
