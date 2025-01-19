from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.booking import Booking, BookingState, DayCapacity

BOOKED_ON = date(2024, 6, 3)
BOOKED_FOR = date(2024, 6, 12)


def a_booking(**changes: object) -> Booking:
    base: dict[str, object] = {
        "owner_code": "WELD1",
        "booked_for": BOOKED_FOR,
        "cylinders": 40,
        "booked_on": BOOKED_ON,
    }
    base.update(changes)
    return Booking(**base)  # type: ignore[arg-type]


def test_a_booking_for_nothing() -> None:
    with pytest.raises(ValidationError, match="at least one cylinder"):
        a_booking(cylinders=0)


def test_a_booking_for_a_day_that_has_gone() -> None:
    with pytest.raises(ValidationError, match="a day that has gone"):
        a_booking(booked_for=date(2024, 6, 1))


def test_an_arrived_booking_names_its_lot() -> None:
    with pytest.raises(ValidationError, match="name the lot"):
        a_booking(state=BookingState.ARRIVED)
    with pytest.raises(ValidationError, match="only an arrived booking"):
        a_booking(lot_number="L2024-0001")
    arrived = a_booking(state=BookingState.ARRIVED, lot_number="L2024-0001")
    assert "as L2024-0001" in arrived.summary()


def test_a_cancelled_booking_frees_the_bench() -> None:
    assert BookingState.BOOKED.holds_capacity
    assert BookingState.ARRIVED.holds_capacity
    assert not BookingState.CANCELLED.holds_capacity


def test_open_and_days_out() -> None:
    booking = a_booking()
    assert booking.is_open
    assert booking.days_out(BOOKED_ON) == 9
    assert booking.days_out(date(2024, 6, 20)) == -8
    assert not a_booking(state=BookingState.CANCELLED).is_open


def test_capacity_arithmetic() -> None:
    day = DayCapacity(BOOKED_FOR, capacity=60, booked=40)
    assert day.free == 20
    assert day.fits(20)
    assert not day.fits(21)
    assert not day.is_full
    assert not day.is_over
    assert "40 of 60 booked, 20 free" in day.describe()


def test_a_full_day() -> None:
    day = DayCapacity(BOOKED_FOR, capacity=60, booked=60)
    assert day.is_full
    assert not day.is_over
    assert day.free == 0
    assert not day.fits(1)


def test_an_oversold_day() -> None:
    day = DayCapacity(BOOKED_FOR, capacity=60, booked=75)
    assert day.is_over
    assert day.free == 0
    assert "75 booked against 60, over" in day.describe()


def test_capacity_is_counted() -> None:
    with pytest.raises(ValidationError, match="counted, not estimated"):
        DayCapacity(BOOKED_FOR, capacity=-1, booked=0)


def test_summaries() -> None:
    assert a_booking().summary() == "2024-06-12 WELD1 40 cylinders (booked)"
