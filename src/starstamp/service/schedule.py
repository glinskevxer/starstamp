"""Promising work, and knowing whether the shop can keep the promise.

The capacity of a day is not a setting. It is what the rigs that are actually
in calibration on that day can get through, so a certificate expiring on the
fourteenth quietly takes a rig's worth of capacity off the fifteenth, and a
booking taken for the fifteenth before anybody noticed is the phone call the
shop makes on the fourteenth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from starstamp.errors import ConflictError, RuleViolationError
from starstamp.model.booking import Booking, DayCapacity
from starstamp.model.calibration import InstrumentKind
from starstamp.store.bookings import BookingRepository
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.db import Book
from starstamp.store.lots import LotRepository
from starstamp.store.owners import OwnerRepository

CITATION = "shop capacity"
PER_RIG_PER_DAY = 24


@dataclass(frozen=True)
class Offer:
    """A day the shop could take work on."""

    day: date
    capacity: DayCapacity

    @property
    def free(self) -> int:
        return self.capacity.free

    def describe(self) -> str:
        return self.capacity.describe()


class ScheduleService:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.bookings = BookingRepository(book.connection)
        self.calibration = CalibrationRepository(book.connection)
        self.owners = OwnerRepository(book.connection)
        self.lots = LotRepository(book.connection)

    def working_rigs(self, day: date) -> list[str]:
        """Test systems whose pressure instruments are in date on a day."""
        working: list[str] = []
        for system in self.calibration.systems():
            held = {
                certificate.instrument for certificate in self.calibration.in_force(system, day)
            }
            if InstrumentKind.PRESSURE_INDICATOR in held:
                working.append(system)
        return working

    def capacity(self, day: date) -> DayCapacity:
        rigs = len(self.working_rigs(day))
        return DayCapacity(
            day=day,
            capacity=rigs * PER_RIG_PER_DAY,
            booked=self.bookings.booked_on_day(day),
        )

    def book_in(
        self,
        owner_code: str,
        day: date,
        cylinders: int,
        today: date,
        *,
        note: str | None = None,
    ) -> Booking:
        """Promise a day's work, or refuse with what is actually free."""
        owner = self.owners.require_open(owner_code, today)
        standing = self.capacity(day)
        if standing.capacity == 0:
            raise RuleViolationError(
                f"no rig is in calibration on {day.isoformat()}, so nothing can be promised",
                CITATION,
            )
        if not standing.fits(cylinders):
            raise RuleViolationError(
                f"{day.isoformat()} has room for {standing.free} more, not {cylinders}",
                CITATION,
            )
        booking = Booking(
            owner_code=owner.code,
            booked_for=day,
            cylinders=cylinders,
            booked_on=today,
            note=note,
        )
        return self.bookings.add(booking, self.owners.id_of(owner.code))

    def arrive(self, booking_id: int, lot_number: str) -> Booking:
        """Tie a booking to the lot that turned up against it."""
        booking = self.bookings.by_id(booking_id)
        lot = self.lots.by_number(lot_number)
        if lot.owner_code != booking.owner_code:
            raise ConflictError(
                f"{lot.number} belongs to {lot.owner_code} and the booking is {booking.owner_code}"
            )
        return self.bookings.arrive(booking_id, self.lots.id_of(lot_number))

    def offers(self, from_day: date, days: int, cylinders: int) -> list[Offer]:
        """The next days that could take a given number of cylinders."""
        found: list[Offer] = []
        for step in range(max(days, 0)):
            day = from_day + timedelta(days=step)
            standing = self.capacity(day)
            if standing.fits(cylinders):
                found.append(Offer(day, standing))
        return found

    def week(self, from_day: date) -> list[DayCapacity]:
        return [self.capacity(from_day + timedelta(days=step)) for step in range(7)]

    def oversold(self, from_day: date, days: int) -> list[DayCapacity]:
        """Days that have more promised than the rigs can do."""
        return [
            standing
            for step in range(max(days, 0))
            if (standing := self.capacity(from_day + timedelta(days=step))).is_over
        ]
