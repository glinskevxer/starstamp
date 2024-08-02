"""Taking a delivery in and sending it back out.

The lot is the shop's own paperwork rather than the regulator's, and it is
where the two halves meet: a cylinder is settled on its lot by the record of
test that decided it, so the front counter can answer what happened to number
thirty one without reading the whole book.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import ConflictError
from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.lot import Lot, LotLine, LotStatus
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.lots import LotRepository
from starstamp.store.owners import OwnerRepository

DISPOSITIONS = {
    Outcome.PASS: "requalified",
    Outcome.CONDEMN: "condemned",
    Outcome.SUSPENDED: "held for repair",
}


@dataclass(frozen=True)
class LotStanding:
    """A lot and how far through it the shop is."""

    lot: Lot
    lines: tuple[LotLine, ...]

    @property
    def settled(self) -> int:
        return sum(1 for line in self.lines if line.is_settled)

    @property
    def outstanding(self) -> int:
        return len(self.lines) - self.settled

    @property
    def is_finished(self) -> bool:
        return bool(self.lines) and self.outstanding == 0

    def describe(self, today: date) -> str:
        head = (
            f"{self.lot.number} {self.lot.status.value}, {self.settled} of {len(self.lines)} "
            f"settled, {self.lot.days_in_shop(today)} days in the shop"
        )
        if self.lot.is_late(today):
            return f"{head}, {self.lot.days_late(today)} days past the promise"
        return head


class ReceivingService:
    """The front counter's half of the shop."""

    def __init__(self, book: Book) -> None:
        self.book = book
        self.lots = LotRepository(book.connection)
        self.cylinders = CylinderRepository(book.connection)
        self.owners = OwnerRepository(book.connection)

    def receive(
        self,
        owner_code: str,
        day: date,
        keys: list[CylinderKey],
        *,
        promised_on: date | None = None,
        carrier: str | None = None,
        note: str | None = None,
    ) -> LotStanding:
        """Book a delivery in and put its cylinders in the shop."""
        owner = self.owners.require_open(owner_code, day)
        number = self.lots.next_number(day.year)
        lot = Lot(
            number=number,
            owner_code=owner.code,
            received_on=day,
            promised_on=promised_on,
            carrier=carrier,
            note=note,
        )
        self.lots.add(lot, self.owners.id_of(owner.code))
        for key in keys:
            cylinder = self.cylinders.by_key(key)
            if cylinder.owner_code != owner.code:
                raise ConflictError(f"{key} belongs to {cylinder.owner_code}, not {owner.code}")
            self.lots.add_line(number, self.cylinders.id_of(key), key, day)
            if cylinder.status is CylinderStatus.IN_SERVICE:
                self.cylinders.set_status(key, CylinderStatus.IN_SHOP)
        return self.standing(number)

    def standing(self, number: str) -> LotStanding:
        return LotStanding(self.lots.by_number(number), tuple(self.lots.lines(number)))

    def settle_from_event(self, event: RequalificationEvent) -> str | None:
        """Settle the cylinder's line on whichever open lot is holding it."""
        cylinder_id = self.cylinders.id_of(event.cylinder)
        for number in self.lots.lots_holding(cylinder_id):
            lot = self.lots.by_number(number)
            if not lot.status.is_open:
                continue
            open_keys = {line.cylinder_key for line in self.lots.open_lines(number)}
            if str(event.cylinder) not in open_keys:
                continue
            self.lots.settle(number, cylinder_id, DISPOSITIONS[event.outcome], event.event_id)
            if lot.status is LotStatus.RECEIVED:
                self.lots.set_status(number, LotStatus.IN_PROGRESS)
            return number
        return None

    def ready(self, number: str) -> LotStanding:
        """Mark a lot ready to go back, once nothing on it is outstanding."""
        standing = self.standing(number)
        if not standing.is_finished:
            raise ConflictError(
                f"{number} still has {standing.outstanding} cylinders with nothing decided"
            )
        self.lots.set_status(number, LotStatus.READY)
        return self.standing(number)

    def return_lot(self, number: str, day: date) -> LotStanding:
        """Send a lot back and put its surviving cylinders back in service."""
        standing = self.standing(number)
        if standing.lot.status is not LotStatus.READY:
            raise ConflictError(f"{number} is {standing.lot.status.value}, not ready to go back")
        for line in standing.lines:
            key = CylinderKey.parse(line.cylinder_key)
            cylinder = self.cylinders.by_key(key)
            if cylinder.status is CylinderStatus.IN_SHOP:
                self.cylinders.set_status(key, CylinderStatus.IN_SERVICE)
        self.lots.set_status(number, LotStatus.RETURNED, day)
        return self.standing(number)

    def open_standing(self) -> list[LotStanding]:
        return [self.standing(lot.number) for lot in self.lots.open_lots()]
