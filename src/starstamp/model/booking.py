"""Work promised to a customer for a particular day.

The shop can put a certain number of cylinders across the bench in a day and
no more, and the number is not a guess: it is the number of test systems times
what one rig gets through. Booking is therefore about capacity rather than
about a calendar, and a booking that would take the day past capacity is
refused rather than accepted and apologised for later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from starstamp.errors import ValidationError


class BookingState(Enum):
    """Where a booking stands."""

    BOOKED = "booked"
    ARRIVED = "arrived"
    CANCELLED = "cancelled"

    @property
    def holds_capacity(self) -> bool:
        """Whether it still takes up room on the bench."""
        return self is not BookingState.CANCELLED


@dataclass(frozen=True)
class Booking:
    """One account bringing a number of cylinders in on a day."""

    owner_code: str
    booked_for: date
    cylinders: int
    booked_on: date
    state: BookingState = BookingState.BOOKED
    lot_number: str | None = None
    note: str | None = None
    booking_id: int | None = None

    def __post_init__(self) -> None:
        if self.cylinders <= 0:
            raise ValidationError("a booking is for at least one cylinder")
        if self.booked_for < self.booked_on:
            raise ValidationError("a booking cannot be made for a day that has gone")
        if self.state is BookingState.ARRIVED and self.lot_number is None:
            raise ValidationError("a booking that arrived has to name the lot it came in on")
        if self.state is not BookingState.ARRIVED and self.lot_number is not None:
            raise ValidationError("only an arrived booking names a lot")

    @property
    def is_open(self) -> bool:
        return self.state is BookingState.BOOKED

    def days_out(self, today: date) -> int:
        return (self.booked_for - today).days

    def summary(self) -> str:
        line = (
            f"{self.booked_for.isoformat()} {self.owner_code} {self.cylinders} cylinders "
            f"({self.state.value})"
        )
        if self.lot_number:
            line = f"{line} as {self.lot_number}"
        return line


@dataclass(frozen=True)
class DayCapacity:
    """What one day can take, and what is already on it."""

    day: date
    capacity: int
    booked: int

    def __post_init__(self) -> None:
        if self.capacity < 0 or self.booked < 0:
            raise ValidationError("capacity and bookings are counted, not estimated")

    @property
    def free(self) -> int:
        return max(self.capacity - self.booked, 0)

    @property
    def is_full(self) -> bool:
        return self.booked >= self.capacity

    @property
    def is_over(self) -> bool:
        return self.booked > self.capacity

    def fits(self, cylinders: int) -> bool:
        return cylinders <= self.free

    def describe(self) -> str:
        if self.is_over:
            return f"{self.day.isoformat()}: {self.booked} booked against {self.capacity}, over"
        return f"{self.day.isoformat()}: {self.booked} of {self.capacity} booked, {self.free} free"
