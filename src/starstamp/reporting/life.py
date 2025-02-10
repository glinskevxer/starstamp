"""One cylinder's whole life, in the order it happened.

Every other report answers a question about a month or an account. This one
answers the question a customer asks on the phone: what has happened to this
cylinder. That means reading five tables and putting them on one timeline,
which nothing else in the book does, and it is the only place where a repair
and a record of test sit side by side.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.cylinder import Cylinder, CylinderKey
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.disposals import DisposalRepository
from starstamp.store.events import EventRepository
from starstamp.store.lots import LotRepository
from starstamp.store.notices import NoticeRepository
from starstamp.store.repairs import RepairRepository
from starstamp.text.table import render_pairs, render_table


@dataclass(frozen=True)
class Entry:
    """One thing that happened, whatever kind of thing it was."""

    day: date
    kind: str
    detail: str
    reference: str | None = None

    def row(self) -> list[str]:
        return [self.day.isoformat(), self.kind, self.reference or "-", self.detail]


@dataclass(frozen=True)
class Life:
    """A cylinder and everything the book holds about it."""

    cylinder: Cylinder
    entries: tuple[Entry, ...]

    @property
    def first_seen(self) -> date | None:
        return self.entries[0].day if self.entries else None

    @property
    def last_seen(self) -> date | None:
        return self.entries[-1].day if self.entries else None

    def of_kind(self, kind: str) -> tuple[Entry, ...]:
        return tuple(entry for entry in self.entries if entry.kind == kind)

    def kinds(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.entries:
            counts[entry.kind] = counts.get(entry.kind, 0) + 1
        return dict(sorted(counts.items()))

    def years_in_service(self, today: date) -> int:
        return (today.year - self.cylinder.manufactured.year) - (
            (today.month, today.day) < (self.cylinder.manufactured.month, 1)
        )


def build(book: Book, key: CylinderKey) -> Life:
    """Read every table that says anything about one cylinder."""
    cylinders = CylinderRepository(book.connection)
    cylinder = cylinders.by_key(key)
    cylinder_id = cylinders.id_of(key)
    entries: list[Entry] = []

    for event in EventRepository(book.connection).for_cylinder(key):
        detail = f"{event.method.label} {event.outcome.value}"
        if event.state.value != "recorded":
            detail = f"{detail} [{event.state.value}]"
        if event.reasons:
            detail = f"{detail}: " + "; ".join(event.reasons)
        entries.append(Entry(event.performed_on, "test", detail, f"record {event.event_id}"))

    for repair in RepairRepository(book.connection).for_cylinder(key):
        detail = repair.kind.label
        if repair.parts:
            detail = f"{detail}, {repair.parts}"
        entries.append(Entry(repair.performed_on, "repair", detail, f"repair {repair.repair_id}"))

    for notice in NoticeRepository(book.connection).for_owner(cylinder.owner_code):
        if notice.cylinder_key != str(key):
            continue
        state = "sent" if notice.state.is_sent else "drafted"
        entries.append(
            Entry(
                notice.raised_on,
                "notice",
                f"{notice.kind.label} {state}",
                f"notice {notice.notice_id}",
            )
        )

    lots = LotRepository(book.connection)
    for number in lots.lots_holding(cylinder_id):
        lot = lots.by_number(number)
        entries.append(Entry(lot.received_on, "received", f"came in on {lot.number}", lot.number))
        if lot.returned_on is not None:
            entries.append(
                Entry(lot.returned_on, "returned", f"went back on {lot.number}", lot.number)
            )

    for day, thousandths, source in cylinders.wall_readings(key):
        entries.append(Entry(day, "wall", f"{thousandths / 1000:.3f} in from {source}", None))

    disposal = DisposalRepository(book.connection).for_cylinder(key)
    if disposal is not None:
        entries.append(
            Entry(
                disposal.performed_on,
                "disposal",
                disposal.method.label,
                f"disposal {disposal.disposal_id}",
            )
        )

    entries.sort(key=lambda entry: (entry.day, entry.kind))
    return Life(cylinder, tuple(entries))


def render(life: Life, today: date) -> str:
    cylinder = life.cylinder
    lines = [
        render_pairs(
            [
                ("cylinder", str(cylinder.key)),
                ("specification", str(cylinder.specification)),
                ("made", cylinder.manufactured.long_form()),
                ("age", f"{life.years_in_service(today)} years"),
                ("service", cylinder.service.name),
                ("owner", cylinder.owner_code),
                ("status", cylinder.status.value),
            ]
        )
    ]
    if not life.entries:
        lines.append("")
        lines.append("nothing has happened to it here")
        return "\n".join(lines)
    lines.append("")
    lines.append(
        render_table(
            ["date", "what", "reference", "detail"],
            [entry.row() for entry in life.entries],
        )
    )
    return "\n".join(lines)
