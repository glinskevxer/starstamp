"""How long a lot takes to get through the shop.

The number the customer asks about, and the one the shop argues about, are not
the same number. The customer means the day they dropped it off to the day
they got it back. The shop means the day it started work to the day it
finished, which is shorter and is not what was promised. Both are here, and
they are named so nobody quotes one and means the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.model.lot import Lot, LotStatus
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.lots import LotRepository
from starstamp.text.table import render_table


@dataclass(frozen=True)
class LotCycle:
    """One lot, from the door to the door."""

    lot: Lot
    first_work: date | None
    last_work: date | None
    cylinders: int

    @property
    def door_to_door(self) -> int | None:
        if self.lot.returned_on is None:
            return None
        return (self.lot.returned_on - self.lot.received_on).days

    @property
    def bench_days(self) -> int | None:
        if self.first_work is None or self.last_work is None:
            return None
        return (self.last_work - self.first_work).days + 1

    @property
    def waiting_to_start(self) -> int | None:
        if self.first_work is None:
            return None
        return (self.first_work - self.lot.received_on).days

    @property
    def waiting_to_go(self) -> int | None:
        if self.last_work is None or self.lot.returned_on is None:
            return None
        return (self.lot.returned_on - self.last_work).days

    @property
    def was_late(self) -> bool:
        if self.lot.promised_on is None or self.lot.returned_on is None:
            return False
        return self.lot.returned_on > self.lot.promised_on

    def row(self) -> list[str]:
        return [
            self.lot.number,
            self.lot.owner_code,
            str(self.cylinders),
            "-" if self.door_to_door is None else str(self.door_to_door),
            "-" if self.waiting_to_start is None else str(self.waiting_to_start),
            "-" if self.bench_days is None else str(self.bench_days),
            "-" if self.waiting_to_go is None else str(self.waiting_to_go),
            "yes" if self.was_late else "no",
        ]


@dataclass(frozen=True)
class Cycles:
    """Every lot that finished in a window."""

    first: date
    last: date
    lots: tuple[LotCycle, ...]

    @property
    def finished(self) -> tuple[LotCycle, ...]:
        return tuple(item for item in self.lots if item.door_to_door is not None)

    def average_door_to_door(self) -> Fraction:
        finished = self.finished
        if not finished:
            return Fraction(0)
        return Fraction(sum(item.door_to_door or 0 for item in finished), len(finished))

    def average_waiting_to_start(self) -> Fraction:
        waited = [item for item in self.finished if item.waiting_to_start is not None]
        if not waited:
            return Fraction(0)
        return Fraction(sum(item.waiting_to_start or 0 for item in waited), len(waited))

    def late(self) -> tuple[LotCycle, ...]:
        return tuple(item for item in self.finished if item.was_late)

    def describe(self) -> str:
        finished = self.finished
        if not finished:
            return f"no lots went back between {self.first} and {self.last}"
        late = len(self.late())
        return (
            f"{len(finished)} lots went back, {float(self.average_door_to_door()):.1f} days "
            f"door to door on average, {float(self.average_waiting_to_start()):.1f} of that "
            f"waiting to start; {late} were late"
        )


def build(book: Book, first: date, last: date) -> Cycles:
    lots = LotRepository(book.connection)
    events = EventRepository(book.connection)

    found: list[LotCycle] = []
    for lot in _every_lot(lots, first, last):
        lines = lots.lines(lot.number)
        days = [
            event.performed_on
            for line in lines
            if line.event_id is not None
            for event in [events.by_id(line.event_id)]
        ]
        found.append(
            LotCycle(
                lot=lot,
                first_work=min(days) if days else None,
                last_work=max(days) if days else None,
                cylinders=len(lines),
            )
        )
    return Cycles(first, last, tuple(found))


def _every_lot(lots: LotRepository, first: date, last: date) -> list[Lot]:
    """Lots that went back in the window, plus the ones still open."""
    returned = [
        lot
        for lot in lots.received_between(date(1900, 1, 1), last)
        if lot.returned_on is not None and first <= lot.returned_on <= last
    ]
    still_here = [lot for lot in lots.open_lots() if lot.status is not LotStatus.RETURNED]
    return sorted(returned + still_here, key=lambda lot: lot.number)


def render(cycles: Cycles) -> str:
    if not cycles.lots:
        return cycles.describe()
    table = render_table(
        ["lot", "owner", "cylinders", "door", "waiting", "bench", "to go", "late"],
        [item.row() for item in cycles.lots],
        right=(2, 3, 4, 5, 6),
    )
    return f"{table}\n\n{cycles.describe()}"
