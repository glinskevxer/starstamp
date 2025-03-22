from datetime import date

import pytest

from starstamp.errors import ConflictError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.method import Method
from starstamp.model.notice import NoticeKind
from starstamp.rules.abandonment import Standing
from starstamp.service.abandoned import AbandonedService
from starstamp.service.receiving import ReceivingService
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.db import Book

from ..support.factories import make_readings
from ..support.shop import DAY, SYSTEM

KEY = CylinderKey("NCI", "A4471")


def a_ready_lot(book: Book) -> None:
    receiving = ReceivingService(book)
    receiving.receive("WELD1", date(2024, 6, 3), [KEY])
    RequalificationService(book).perform(
        RequalificationRequest(
            key=KEY,
            day=DAY,
            technician_badge="JT7",
            method=Method.VOLUMETRIC,
            system_code=SYSTEM,
            readings=make_readings(),
        )
    )
    receiving.ready("L2024-0001")


def test_a_lot_just_finished_is_in_hand(shop_book: Book) -> None:
    a_ready_lot(shop_book)
    found = AbandonedService(shop_book).left_behind(date(2024, 6, 20))
    assert len(found) == 1
    assert found[0].standing.standing is Standing.IN_HAND


def test_a_lot_left_six_months_needs_a_letter(shop_book: Book) -> None:
    a_ready_lot(shop_book)
    service = AbandonedService(shop_book)
    overdue = service.needing_a_letter(date(2025, 1, 1))
    assert len(overdue) == 1
    assert "nobody has written to WELD1" in overdue[0].describe()


def test_writing_the_letter_starts_the_second_clock(shop_book: Book) -> None:
    a_ready_lot(shop_book)
    service = AbandonedService(shop_book)
    notice = service.write_to("L2024-0001", date(2025, 1, 1))
    assert notice.kind is NoticeKind.UNCOLLECTED
    assert "L2024-0001" in notice.body
    assert service.needing_a_letter(date(2025, 1, 2)) == []
    found = service.left_behind(date(2025, 1, 2))
    assert found[0].standing.standing is Standing.WRITTEN_TO


def test_a_lot_becomes_abandoned_after_the_second_clock(shop_book: Book) -> None:
    a_ready_lot(shop_book)
    service = AbandonedService(shop_book)
    service.write_to("L2024-0001", date(2025, 1, 1))
    assert service.abandoned(date(2025, 2, 1)) == []
    abandoned = service.abandoned(date(2025, 4, 1))
    assert len(abandoned) == 1
    assert "did not come" in abandoned[0].describe()


def test_the_same_lot_is_only_written_about_once(shop_book: Book) -> None:
    a_ready_lot(shop_book)
    service = AbandonedService(shop_book)
    service.write_to("L2024-0001", date(2025, 1, 1))
    with pytest.raises(ConflictError, match="already been written about"):
        service.write_to("L2024-0001", date(2025, 2, 1))


def test_a_lot_still_being_worked_on(shop_book: Book) -> None:
    ReceivingService(shop_book).receive("WELD1", date(2024, 6, 3), [KEY])
    service = AbandonedService(shop_book)
    assert service.left_behind(date(2025, 1, 1)) == []
    with pytest.raises(ConflictError, match="not waiting to go back"):
        service.write_to("L2024-0001", date(2025, 1, 1))


def test_a_returned_lot_drops_off(shop_book: Book) -> None:
    a_ready_lot(shop_book)
    ReceivingService(shop_book).return_lot("L2024-0001", date(2024, 6, 20))
    assert AbandonedService(shop_book).left_behind(date(2025, 1, 1)) == []
