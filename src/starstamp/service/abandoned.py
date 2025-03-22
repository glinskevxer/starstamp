"""Chasing the lots nobody has collected.

This is the only service that writes a letter as a step in a process rather
than as a record of something that happened. The letter is what starts the
second clock, so it has to exist before the shop can say a lot is abandoned,
and the shop has to be able to show which letter it was.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import ConflictError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.lot import Lot, LotStatus
from starstamp.model.notice import Notice, NoticeKind
from starstamp.rules.abandonment import Abandonment, Standing, standing_for
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.lots import LotRepository
from starstamp.store.notices import NoticeRepository
from starstamp.store.owners import OwnerRepository


def uncollected_body(lot: Lot, standing: Abandonment) -> str:
    return (
        f"Lot {lot.number} has been ready to collect since "
        f"{(standing.ready_since or lot.received_on).isoformat()} and is still here.\n"
        f"Please arrange collection. If we do not hear from you within sixty days we will "
        f"treat the cylinders as abandoned and dispose of them."
    )


@dataclass(frozen=True)
class LeftBehind:
    """One lot and where it has got to."""

    lot: Lot
    standing: Abandonment
    notice: Notice | None

    def describe(self) -> str:
        return self.standing.describe()


class AbandonedService:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.lots = LotRepository(book.connection)
        self.notices = NoticeRepository(book.connection)
        self.owners = OwnerRepository(book.connection)
        self.cylinders = CylinderRepository(book.connection)

    def letter_for(self, lot: Lot) -> Notice | None:
        """The uncollected letter already written about a lot, if there is one."""
        for notice in self.notices.for_owner(lot.owner_code):
            if notice.kind is NoticeKind.UNCOLLECTED and lot.number in notice.body:
                return notice
        return None

    def left_behind(self, today: date) -> list[LeftBehind]:
        """Every lot sitting ready, with where each one has got to."""
        found: list[LeftBehind] = []
        for lot in self.lots.open_lots():
            if lot.status is not LotStatus.READY:
                continue
            notice = self.letter_for(lot)
            standing = standing_for(
                lot, today, written_on=None if notice is None else notice.raised_on
            )
            found.append(LeftBehind(lot, standing, notice))
        return sorted(found, key=lambda item: -item.standing.days_ready)

    def write_to(self, lot_number: str, today: date) -> Notice:
        """Write the letter that starts the second clock."""
        lot = self.lots.by_number(lot_number)
        if lot.status is not LotStatus.READY:
            raise ConflictError(f"{lot.number} is {lot.status.value}, not waiting to go back")
        if self.letter_for(lot) is not None:
            raise ConflictError(f"{lot.number} has already been written about")
        lines = self.lots.lines(lot.number)
        if not lines:
            raise ConflictError(f"{lot.number} has no cylinders on it")
        standing = standing_for(lot, today)
        key = CylinderKey.parse(lines[0].cylinder_key)
        notice = Notice(
            owner_code=lot.owner_code,
            cylinder_key=str(key),
            kind=NoticeKind.UNCOLLECTED,
            raised_on=today,
            body=uncollected_body(lot, standing),
        )
        return self.notices.add(
            notice, self.owners.id_of(lot.owner_code), self.cylinders.id_of(key)
        )

    def abandoned(self, today: date) -> list[LeftBehind]:
        return [
            item for item in self.left_behind(today) if item.standing.standing is Standing.ABANDONED
        ]

    def needing_a_letter(self, today: date) -> list[LeftBehind]:
        return [
            item for item in self.left_behind(today) if item.standing.standing is Standing.OVERDUE
        ]
