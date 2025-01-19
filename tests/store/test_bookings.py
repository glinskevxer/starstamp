from datetime import date

import pytest

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.booking import Booking, BookingState
from starstamp.model.lot import Lot
from starstamp.store.bookings import BookingRepository
from starstamp.store.db import Book
from starstamp.store.lots import LotRepository
from starstamp.store.owners import OwnerRepository

BOOKED_ON = date(2024, 6, 3)
BOOKED_FOR = date(2024, 6, 12)


@pytest.fixture
def bookings(book: Book, owners: OwnerRepository) -> BookingRepository:
    return BookingRepository(book.connection)


def a_booking(**changes: object) -> Booking:
    base: dict[str, object] = {
        "owner_code": "WELD1",
        "booked_for": BOOKED_FOR,
        "cylinders": 40,
        "booked_on": BOOKED_ON,
    }
    base.update(changes)
    return Booking(**base)  # type: ignore[arg-type]


def test_a_booking_round_trips(bookings: BookingRepository, owners: OwnerRepository) -> None:
    written = bookings.add(a_booking(note="collect on the way back"), owners.id_of("WELD1"))
    assert written.booking_id is not None
    read_back = bookings.by_id(written.booking_id)
    assert read_back.cylinders == 40
    assert read_back.owner_code == "WELD1"
    assert read_back.note == "collect on the way back"


def test_what_is_booked_on_a_day(bookings: BookingRepository, owners: OwnerRepository) -> None:
    bookings.add(a_booking(), owners.id_of("WELD1"))
    bookings.add(a_booking(cylinders=15), owners.id_of("WELD1"))
    assert bookings.booked_on_day(BOOKED_FOR) == 55
    assert bookings.booked_on_day(date(2024, 6, 13)) == 0


def test_a_cancelled_booking_stops_counting(
    bookings: BookingRepository, owners: OwnerRepository
) -> None:
    written = bookings.add(a_booking(), owners.id_of("WELD1"))
    assert written.booking_id is not None
    bookings.cancel(written.booking_id, "customer put it off")
    assert bookings.booked_on_day(BOOKED_FOR) == 0
    assert bookings.by_id(written.booking_id).state is BookingState.CANCELLED
    with pytest.raises(ConflictError, match="cancelled already"):
        bookings.cancel(written.booking_id)


def test_a_booking_that_arrives(
    bookings: BookingRepository, owners: OwnerRepository, book: Book
) -> None:
    lots = LotRepository(book.connection)
    lots.add(
        Lot(number="L2024-0001", owner_code="WELD1", received_on=BOOKED_FOR),
        owners.id_of("WELD1"),
    )
    written = bookings.add(a_booking(), owners.id_of("WELD1"))
    assert written.booking_id is not None
    arrived = bookings.arrive(written.booking_id, lots.id_of("L2024-0001"))
    assert arrived.state is BookingState.ARRIVED
    assert arrived.lot_number == "L2024-0001"
    assert bookings.booked_on_day(BOOKED_FOR) == 40
    with pytest.raises(ConflictError, match="already came in"):
        bookings.arrive(written.booking_id, lots.id_of("L2024-0001"))


def test_a_cancelled_booking_cannot_arrive(
    bookings: BookingRepository, owners: OwnerRepository, book: Book
) -> None:
    lots = LotRepository(book.connection)
    lots.add(
        Lot(number="L2024-0001", owner_code="WELD1", received_on=BOOKED_FOR),
        owners.id_of("WELD1"),
    )
    written = bookings.add(a_booking(), owners.id_of("WELD1"))
    assert written.booking_id is not None
    bookings.cancel(written.booking_id)
    with pytest.raises(ConflictError, match="was cancelled"):
        bookings.arrive(written.booking_id, lots.id_of("L2024-0001"))


def test_listings(bookings: BookingRepository, owners: OwnerRepository) -> None:
    bookings.add(a_booking(), owners.id_of("WELD1"))
    bookings.add(a_booking(booked_for=date(2024, 7, 1)), owners.id_of("WELD1"))
    assert len(bookings.between(date(2024, 6, 1), date(2024, 6, 30))) == 1
    assert len(bookings.for_owner("weld1")) == 2


def test_bookings_nobody_honoured(bookings: BookingRepository, owners: OwnerRepository) -> None:
    bookings.add(a_booking(), owners.id_of("WELD1"))
    assert bookings.missed(BOOKED_FOR) == []
    missed = bookings.missed(date(2024, 6, 13))
    assert len(missed) == 1
    assert missed[0].owner_code == "WELD1"


def test_a_missing_booking(bookings: BookingRepository) -> None:
    with pytest.raises(NotFoundError, match="no booking 99"):
        bookings.by_id(99)
