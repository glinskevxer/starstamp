"""Drafting the letters the shop owes its customers.

The condemnation letters are the ones that have to go out, and the shop finds
them the same way an inspector would: every standing condemnation with no
notice against it. Nothing here sends anything by itself. A letter is drafted,
somebody reads it, and sending it is a separate act with its own date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.cylinder import Cylinder, CylinderStatus
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.notice import Notice, NoticeKind
from starstamp.service.fill import FillService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.notices import NoticeRepository
from starstamp.store.owners import OwnerRepository


def condemnation_body(cylinder: Cylinder, event: RequalificationEvent) -> str:
    reasons = "\n".join(f"  - {reason}" for reason in event.reasons)
    return (
        f"Cylinder {cylinder.key}, {cylinder.specification}, was requalified on "
        f"{event.performed_on.isoformat()} and did not pass.\n"
        f"It has been condemned and may not be filled again.\n\n"
        f"Why:\n{reasons}\n\n"
        f"The cylinder is held here until you tell us what to do with it. We can render it "
        f"incapable of holding pressure and scrap it, or return it to you rendered unusable."
    )


def due_soon_body(cylinder: Cylinder, due: str, months: int) -> str:
    return (
        f"Cylinder {cylinder.key}, {cylinder.specification} in {cylinder.service} service, "
        f"falls due for requalification in {due} ({months} months from now).\n"
        f"It may be filled through the end of that month and not after."
    )


def out_of_test_body(cylinder: Cylinder, due: str) -> str:
    return (
        f"Cylinder {cylinder.key} went out of test in {due} and may not be filled.\n"
        f"Send it in and we will requalify it."
    )


@dataclass(frozen=True)
class Drafted:
    """What a run of the drafter produced."""

    notices: tuple[Notice, ...]

    @property
    def count(self) -> int:
        return len(self.notices)

    def of_kind(self, kind: NoticeKind) -> tuple[Notice, ...]:
        return tuple(notice for notice in self.notices if notice.kind is kind)

    def describe(self) -> str:
        if not self.notices:
            return "nothing to write"
        lines = [f"{self.count} notices drafted"]
        lines.extend(f"  {notice.summary()}" for notice in self.notices)
        return "\n".join(lines)


class NoticeService:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.notices = NoticeRepository(book.connection)
        self.events = EventRepository(book.connection)
        self.cylinders = CylinderRepository(book.connection)
        self.owners = OwnerRepository(book.connection)
        self.fill = FillService(book)

    def draft_condemnations(self, day: date) -> Drafted:
        """One letter for every standing condemnation nobody has written about."""
        drafted: list[Notice] = []
        for cylinder in self.cylinders.with_status(CylinderStatus.CONDEMNED):
            for event in self.events.for_cylinder(cylinder.key, standing_only=True):
                if event.outcome is not Outcome.CONDEMN or event.event_id is None:
                    continue
                if self.notices.for_event(event.event_id):
                    continue
                notice = Notice(
                    owner_code=cylinder.owner_code,
                    cylinder_key=str(cylinder.key),
                    kind=NoticeKind.CONDEMNATION,
                    raised_on=day,
                    body=condemnation_body(cylinder, event),
                    event_id=event.event_id,
                )
                drafted.append(
                    self.notices.add(
                        notice,
                        self.owners.id_of(cylinder.owner_code),
                        self.cylinders.id_of(cylinder.key),
                    )
                )
        return Drafted(tuple(drafted))

    def draft_reminders(self, day: date, months: int, *, owner_code: str | None = None) -> Drafted:
        """Letters about what is falling due, and what has already fallen out."""
        drafted: list[Notice] = []
        for row in self.fill.due_within(day, months, owner_code=owner_code):
            if row.due is None or row.months_left is None:
                continue
            cylinder = row.cylinder
            if row.overdue:
                kind = NoticeKind.OUT_OF_TEST
                body = out_of_test_body(cylinder, row.due.long_form())
            else:
                kind = NoticeKind.DUE_SOON
                body = due_soon_body(cylinder, row.due.long_form(), row.months_left)
            notice = Notice(
                owner_code=cylinder.owner_code,
                cylinder_key=str(cylinder.key),
                kind=kind,
                raised_on=day,
                body=body,
            )
            drafted.append(
                self.notices.add(
                    notice,
                    self.owners.id_of(cylinder.owner_code),
                    self.cylinders.id_of(cylinder.key),
                )
            )
        return Drafted(tuple(drafted))

    def send(self, notice_id: int, day: date) -> Notice:
        return self.notices.send(notice_id, day)

    def overdue_letters(self, day: date) -> list[Notice]:
        """Condemnation letters the shop is late sending."""
        return [notice for notice in self.notices.unsent() if notice.is_late(day)]


def _condemned() -> CylinderStatus:
    return CylinderStatus.CONDEMNED
