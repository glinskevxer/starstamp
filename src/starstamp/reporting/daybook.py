"""One day, everything that happened in it.

The shop's own question at five o'clock. It reads across six tables because
that is what a day is: cylinders in, cylinders tested, valves changed, gas put
in, letters written, cylinders back out. Nothing here is derived or judged;
the day either happened or it did not.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.event import Outcome
from starstamp.store.db import Book
from starstamp.store.disposals import DisposalRepository
from starstamp.store.events import EventRepository
from starstamp.store.fills import FillRepository
from starstamp.store.lots import LotRepository
from starstamp.store.notices import NoticeRepository
from starstamp.store.repairs import RepairRepository
from starstamp.store.transfers import TransferRepository
from starstamp.text.table import render_table


@dataclass(frozen=True)
class DayLine:
    """One thing that happened, with what it was."""

    kind: str
    subject: str
    detail: str

    def row(self) -> list[str]:
        return [self.kind, self.subject, self.detail]


@dataclass(frozen=True)
class Daybook:
    """A day's work, in the order the shop does it."""

    day: date
    lines: tuple[DayLine, ...]

    @property
    def is_quiet(self) -> bool:
        return not self.lines

    def of_kind(self, kind: str) -> tuple[DayLine, ...]:
        return tuple(line for line in self.lines if line.kind == kind)

    def counts(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for line in self.lines:
            found[line.kind] = found.get(line.kind, 0) + 1
        return dict(sorted(found.items()))

    def describe(self) -> str:
        if self.is_quiet:
            return f"nothing happened on {self.day.isoformat()}"
        counts = self.counts()
        parts = ", ".join(f"{count} {kind}" for kind, count in counts.items())
        return f"{self.day.isoformat()}: {parts}"


def build(book: Book, day: date) -> Daybook:
    lines: list[DayLine] = []

    lots = LotRepository(book.connection)
    for lot in lots.received_between(day, day):
        lines.append(
            DayLine(
                "received", lot.number, f"{lot.owner_code}, {len(lots.lines(lot.number))} cylinders"
            )
        )
    for lot in lots.open_lots():
        if lot.returned_on == day:
            lines.append(DayLine("returned", lot.number, lot.owner_code))

    for event in EventRepository(book.connection).on_day(day):
        detail = f"{event.method.label} {event.outcome.value}"
        if event.outcome is Outcome.CONDEMN and event.reasons:
            detail = f"{detail}: {event.reasons[0]}"
        if not event.state.stands:
            detail = f"{detail} [{event.state.value}]"
        lines.append(DayLine("test", str(event.cylinder), detail))

    for repair in RepairRepository(book.connection).between(day, day):
        lines.append(DayLine("repair", repair.cylinder_key, repair.kind.label))

    for fill in FillRepository(book.connection).between(day, day):
        detail = (
            f"{fill.service} to {fill.pressure}"
            if not fill.is_by_weight
            else f"{fill.service}, {(fill.weight_hundredths_lb or 0) / 100:.2f} lb"
        )
        lines.append(DayLine("fill", fill.cylinder_key, detail))

    for transfer in TransferRepository(book.connection).between(day, day):
        lines.append(
            DayLine(
                "transfer",
                transfer.cylinder_key,
                f"{transfer.from_owner or 'taken on'} to {transfer.to_owner}",
            )
        )

    for disposal in DisposalRepository(book.connection).between(day, day):
        lines.append(DayLine("disposal", disposal.cylinder_key, disposal.method.label))

    for notice in NoticeRepository(book.connection).unsent():
        if notice.raised_on == day:
            lines.append(DayLine("notice", notice.cylinder_key, notice.kind.label))

    return Daybook(day, tuple(lines))


def render(daybook: Daybook) -> str:
    if daybook.is_quiet:
        return daybook.describe()
    table = render_table(["what", "subject", "detail"], [line.row() for line in daybook.lines])
    return f"{daybook.describe()}\n\n{table}"
