from datetime import date

import pytest

from starstamp.errors import ConflictError, RuleViolationError
from starstamp.model.calibration import InstrumentKind
from starstamp.model.cylinder import CylinderKey
from starstamp.service.receiving import ReceivingService
from starstamp.service.schedule import PER_RIG_PER_DAY, ScheduleService
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.db import Book

from ..support.factories import make_certificate

TODAY = date(2024, 6, 3)
DAY = date(2024, 6, 12)
KEY = CylinderKey("NCI", "A4471")


def test_capacity_comes_from_the_rigs_in_calibration(shop_book: Book) -> None:
    service = ScheduleService(shop_book)
    assert service.working_rigs(DAY) == ["WJ-1"]
    assert service.capacity(DAY).capacity == PER_RIG_PER_DAY


def test_a_second_rig_doubles_it(shop_book: Book) -> None:
    CalibrationRepository(shop_book.connection).add_certificate(
        make_certificate(InstrumentKind.PRESSURE_INDICATOR, system_code="WJ-2", serial="PG-9")
    )
    assert ScheduleService(shop_book).capacity(DAY).capacity == PER_RIG_PER_DAY * 2


def test_a_rig_out_of_calibration_takes_its_capacity_with_it(shop_book: Book) -> None:
    shop_book.connection.execute(
        "UPDATE calibration_certificate SET valid_until = '2024-06-11'"
        " WHERE instrument = 'pressure_indicator'"
    )
    service = ScheduleService(shop_book)
    assert service.capacity(DAY).capacity == 0
    with pytest.raises(RuleViolationError, match="no rig is in calibration"):
        service.book_in("WELD1", DAY, 10, TODAY)


def test_booking_takes_room_off_the_day(shop_book: Book) -> None:
    service = ScheduleService(shop_book)
    service.book_in("WELD1", DAY, 10, TODAY)
    standing = service.capacity(DAY)
    assert standing.booked == 10
    assert standing.free == PER_RIG_PER_DAY - 10


def test_a_booking_past_capacity_says_what_is_free(shop_book: Book) -> None:
    service = ScheduleService(shop_book)
    service.book_in("WELD1", DAY, 20, TODAY)
    with pytest.raises(RuleViolationError, match="room for 4 more, not 10"):
        service.book_in("WELD1", DAY, 10, TODAY)


def test_a_cancelled_booking_gives_the_room_back(shop_book: Book) -> None:
    service = ScheduleService(shop_book)
    booking = service.book_in("WELD1", DAY, 20, TODAY)
    assert booking.booking_id is not None
    service.bookings.cancel(booking.booking_id, "put off")
    assert service.capacity(DAY).free == PER_RIG_PER_DAY


def test_arriving_ties_the_booking_to_the_lot(shop_book: Book) -> None:
    service = ScheduleService(shop_book)
    booking = service.book_in("WELD1", DAY, 1, TODAY)
    assert booking.booking_id is not None
    ReceivingService(shop_book).receive("WELD1", DAY, [KEY])
    arrived = service.arrive(booking.booking_id, "L2024-0001")
    assert arrived.lot_number == "L2024-0001"


def test_a_lot_belonging_to_somebody_else(shop_book: Book) -> None:
    from starstamp.model.owner import OwnerAccount
    from starstamp.store.owners import OwnerRepository

    owners = OwnerRepository(shop_book.connection)
    owners.add(OwnerAccount(code="FIRE7", name="Sanpete Fire", opened_on=date(2020, 1, 1)))
    service = ScheduleService(shop_book)
    booking = service.book_in("FIRE7", DAY, 1, TODAY)
    assert booking.booking_id is not None
    ReceivingService(shop_book).receive("WELD1", DAY, [KEY])
    with pytest.raises(ConflictError, match="belongs to WELD1"):
        service.arrive(booking.booking_id, "L2024-0001")


def test_the_days_that_could_take_the_work(shop_book: Book) -> None:
    service = ScheduleService(shop_book)
    service.book_in("WELD1", DAY, 20, TODAY)
    offers = service.offers(DAY, 3, 10)
    assert [offer.day.day for offer in offers] == [13, 14]
    assert "of 24 booked" in offers[0].describe()


def test_the_week_and_the_oversold_days(shop_book: Book) -> None:
    service = ScheduleService(shop_book)
    service.book_in("WELD1", DAY, 24, TODAY)
    week = service.week(DAY)
    assert len(week) == 7
    assert week[0].is_full
    assert service.oversold(DAY, 7) == []
    shop_book.connection.execute(
        "INSERT INTO booking (owner_id, booked_for, booked_on, cylinders, state)"
        " VALUES ((SELECT id FROM owner_account WHERE code = 'WELD1'), '2024-06-12',"
        " '2024-06-03', 5, 'booked')"
    )
    assert len(service.oversold(DAY, 7)) == 1


def test_an_account_that_is_not_open(shop_book: Book) -> None:
    from starstamp.errors import NotFoundError

    with pytest.raises(NotFoundError):
        ScheduleService(shop_book).book_in("FIRE7", DAY, 1, TODAY)


def test_the_shop_can_set_what_one_rig_gets_through(shop_book: Book) -> None:
    from starstamp.model.settings import CAPACITY_PER_RIG
    from starstamp.store.settings import SettingRepository

    SettingRepository(shop_book.connection).set(CAPACITY_PER_RIG, "40", date(2024, 1, 1))
    service = ScheduleService(shop_book)
    assert service.per_rig(DAY) == 40
    assert service.capacity(DAY).capacity == 40


def test_a_capacity_set_later_does_not_reach_back(shop_book: Book) -> None:
    from starstamp.model.settings import CAPACITY_PER_RIG
    from starstamp.store.settings import SettingRepository

    SettingRepository(shop_book.connection).set(CAPACITY_PER_RIG, "40", date(2025, 1, 1))
    service = ScheduleService(shop_book)
    assert service.capacity(DAY).capacity == PER_RIG_PER_DAY
    assert service.capacity(date(2025, 6, 1)).capacity == 40
