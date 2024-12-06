"""Dealing with a condemned cylinder.

The rule the shop actually has to keep is short: a condemned cylinder gets
rendered incapable of holding pressure, or it goes back to its owner rendered,
and either way it happens within a month. What makes this worth a service
rather than a repository call is that the clock starts at the condemning
record of test, which is somewhere else entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import Cylinder, CylinderKey, CylinderStatus
from starstamp.model.disposal import RENDER_WITHIN_DAYS, Disposal, DisposalMethod
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.facility import normalise_badge
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.disposals import DisposalRepository
from starstamp.store.events import EventRepository
from starstamp.store.facility import TechnicianRepository

CITATION = "49 CFR 180.205(i)"


@dataclass(frozen=True)
class Outstanding:
    """A condemned cylinder nobody has dealt with yet."""

    cylinder: Cylinder
    condemned_on: date
    days_waiting: int
    due_by: date

    @property
    def is_late(self) -> bool:
        return self.days_waiting > (self.due_by - self.condemned_on).days

    def describe(self) -> str:
        line = (
            f"{self.cylinder.key} condemned {self.condemned_on.isoformat()}, "
            f"{self.days_waiting} days ago, due by {self.due_by.isoformat()}"
        )
        return f"{line}, LATE" if self.is_late else line


class DisposalService:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.cylinders = CylinderRepository(book.connection)
        self.disposals = DisposalRepository(book.connection)
        self.events = EventRepository(book.connection)
        self.technicians = TechnicianRepository(book.connection)

    def condemning_event(self, key: CylinderKey) -> RequalificationEvent:
        """The standing record of test that condemned a cylinder."""
        for event in reversed(self.events.for_cylinder(key, standing_only=True)):
            if event.outcome is Outcome.CONDEMN:
                return event
        raise RuleViolationError(
            f"{key} has no standing condemnation, so there is nothing to deal with", CITATION
        )

    def dispose(
        self,
        key: CylinderKey,
        method: DisposalMethod,
        day: date,
        technician_badge: str,
        *,
        witness_badge: str | None = None,
        scrap_ticket: str | None = None,
        returned_to_owner: bool = False,
        note: str | None = None,
    ) -> Disposal:
        cylinder = self.cylinders.by_key(key)
        if cylinder.status is not CylinderStatus.CONDEMNED:
            raise RuleViolationError(
                f"{key} reads {cylinder.status.value}; only a condemned cylinder is dealt with",
                CITATION,
            )
        event = self.condemning_event(key)
        technician = self.technicians.by_badge(technician_badge)
        witness = None if witness_badge is None else normalise_badge(witness_badge)
        disposal = Disposal(
            cylinder_key=str(key),
            method=method,
            performed_on=day,
            technician_badge=technician.badge,
            condemned_on=event.performed_on,
            witness_badge=witness,
            scrap_ticket=scrap_ticket,
            returned_to_owner=returned_to_owner,
            note=note,
        )
        written = self.disposals.add(disposal, self.cylinders.id_of(key), event.event_id)
        if method.renders_it_useless:
            self.cylinders.set_status(key, CylinderStatus.SCRAPPED)
        return written

    def outstanding(self, today: date) -> list[Outstanding]:
        """Condemned cylinders with nothing recorded against them yet."""
        rows: list[Outstanding] = []
        for cylinder in self.cylinders.with_status(CylinderStatus.CONDEMNED):
            if self.disposals.for_cylinder(cylinder.key) is not None:
                continue
            try:
                event = self.condemning_event(cylinder.key)
            except RuleViolationError:
                continue
            rows.append(
                Outstanding(
                    cylinder=cylinder,
                    condemned_on=event.performed_on,
                    days_waiting=(today - event.performed_on).days,
                    due_by=event.performed_on + timedelta(days=RENDER_WITHIN_DAYS),
                )
            )
        return sorted(rows, key=lambda row: row.condemned_on)

    def late(self, today: date) -> list[Outstanding]:
        return [row for row in self.outstanding(today) if row.is_late]
