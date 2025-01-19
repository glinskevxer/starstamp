"""Reading and writing bookings."""

from __future__ import annotations

import sqlite3
from datetime import date

from starstamp.errors import ConflictError
from starstamp.model.booking import Booking, BookingState
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_text,
    as_text,
    day_text,
)


def row_to_booking(row: sqlite3.Row) -> Booking:
    return Booking(
        owner_code=as_text(row["owner_code"]),
        booked_for=as_day(row["booked_for"]),
        cylinders=as_int(row["cylinders"]),
        booked_on=as_day(row["booked_on"]),
        state=BookingState(as_text(row["state"])),
        lot_number=as_optional_text(row["lot_number"]),
        note=as_optional_text(row["note"]),
        booking_id=as_int(row["id"]),
    )


class BookingRepository(Repository):
    _SELECT = (
        "SELECT b.*, o.code AS owner_code, l.number AS lot_number FROM booking b"
        " JOIN owner_account o ON o.id = b.owner_id"
        " LEFT JOIN lot l ON l.id = b.lot_id"
    )

    def add(self, booking: Booking, owner_id: int) -> Booking:
        cursor = self.connection.execute(
            "INSERT INTO booking (owner_id, booked_for, booked_on, cylinders, state, note)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                owner_id,
                day_text(booking.booked_for),
                day_text(booking.booked_on),
                booking.cylinders,
                booking.state.value,
                booking.note,
            ),
        )
        return self.by_id(int(cursor.lastrowid or 0))

    def by_id(self, booking_id: int) -> Booking:
        return row_to_booking(
            self._one(f"{self._SELECT} WHERE b.id = ?", (booking_id,), f"no booking {booking_id}")
        )

    def on_day(self, day: date) -> list[Booking]:
        rows = self._all(f"{self._SELECT} WHERE b.booked_for = ? ORDER BY b.id", (day_text(day),))
        return [row_to_booking(row) for row in rows]

    def between(self, first: date, last: date) -> list[Booking]:
        rows = self._all(
            f"{self._SELECT} WHERE b.booked_for BETWEEN ? AND ? ORDER BY b.booked_for, b.id",
            (day_text(first), day_text(last)),
        )
        return [row_to_booking(row) for row in rows]

    def for_owner(self, owner_code: str) -> list[Booking]:
        rows = self._all(
            f"{self._SELECT} WHERE o.code = ? ORDER BY b.booked_for, b.id",
            (owner_code.upper(),),
        )
        return [row_to_booking(row) for row in rows]

    def booked_on_day(self, day: date) -> int:
        """Cylinders promised for a day, leaving out anything cancelled."""
        return sum(
            booking.cylinders for booking in self.on_day(day) if booking.state.holds_capacity
        )

    def arrive(self, booking_id: int, lot_id: int) -> Booking:
        booking = self.by_id(booking_id)
        if booking.state is BookingState.CANCELLED:
            raise ConflictError(f"booking {booking_id} was cancelled")
        if booking.state is BookingState.ARRIVED:
            raise ConflictError(f"booking {booking_id} already came in on {booking.lot_number}")
        self.connection.execute(
            "UPDATE booking SET state = ?, lot_id = ? WHERE id = ?",
            (BookingState.ARRIVED.value, lot_id, booking_id),
        )
        return self.by_id(booking_id)

    def cancel(self, booking_id: int, note: str | None = None) -> Booking:
        booking = self.by_id(booking_id)
        if booking.state is BookingState.ARRIVED:
            raise ConflictError(f"booking {booking_id} came in already")
        if booking.state is BookingState.CANCELLED:
            raise ConflictError(f"booking {booking_id} was cancelled already")
        self.connection.execute(
            "UPDATE booking SET state = ?, note = ? WHERE id = ?",
            (BookingState.CANCELLED.value, note or booking.note, booking_id),
        )
        return self.by_id(booking_id)

    def missed(self, today: date) -> list[Booking]:
        """Bookings whose day has gone and whose cylinders never turned up."""
        rows = self._all(
            f"{self._SELECT} WHERE b.booked_for < ? AND b.state = ? ORDER BY b.booked_for",
            (day_text(today), BookingState.BOOKED.value),
        )
        return [row_to_booking(row) for row in rows]
