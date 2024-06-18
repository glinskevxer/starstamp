from datetime import date

import pytest

from starstamp.errors import ConflictError, ValidationError
from starstamp.model.calibration import InstrumentKind
from starstamp.model.cylinder import CylinderKey
from starstamp.model.event import EventState, Outcome
from starstamp.model.method import Method
from starstamp.model.service import NITROGEN
from starstamp.service.fill import FillService
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.service.restate import RestatementService
from starstamp.store.db import Book

from ..support.factories import make_readings
from ..support.shop import DAY, SYSTEM

KEY = CylinderKey("NCI", "A4471")


def requalify(book: Book, day: date = DAY) -> None:
    RequalificationService(book).perform(
        RequalificationRequest(
            key=KEY,
            day=day,
            technician_badge="JT7",
            method=Method.VOLUMETRIC,
            system_code=SYSTEM,
            readings=make_readings(),
        )
    )


def certificate_id(book: Book) -> int:
    from starstamp.store.calibration import CalibrationRepository

    return CalibrationRepository(book.connection).id_of(
        SYSTEM, InstrumentKind.CALIBRATED_CYLINDER, "CAL-1"
    )


def test_a_restatement_pulls_the_work_it_no_longer_covers(shop_book: Book) -> None:
    requalify(shop_book)
    service = RestatementService(shop_book)
    result = service.restate_certificate(
        certificate_id(shop_book), date(2024, 6, 1), "calibration house restated the volume"
    )
    assert result.touched == 1
    assert "1 records" in result.describe()
    history = service.events.for_cylinder(KEY)
    assert [event.state for event in history] == [EventState.REVERSED, EventState.REPLACEMENT]


def test_the_replacement_carries_the_reason_and_no_verdict(shop_book: Book) -> None:
    requalify(shop_book)
    service = RestatementService(shop_book)
    result = service.restate_certificate(certificate_id(shop_book), date(2024, 6, 1), "restated")
    replacement = result.replacements[0]
    assert replacement.outcome is Outcome.SUSPENDED
    assert "restated to end 2024-06-01" in replacement.reasons[0]
    assert replacement.reverses == result.reversed_ids[0]


def test_the_cylinder_is_no_longer_fillable_afterwards(shop_book: Book) -> None:
    requalify(shop_book)
    assert FillService(shop_book).decision(KEY, NITROGEN, date(2024, 7, 1)).allowed
    RestatementService(shop_book).restate_certificate(
        certificate_id(shop_book), date(2024, 6, 1), "restated"
    )
    decision = FillService(shop_book).decision(KEY, NITROGEN, date(2024, 7, 1))
    assert not decision.allowed
    assert "no standing requalification" in decision.refusals


def test_work_outside_the_window_is_left_alone(shop_book: Book) -> None:
    requalify(shop_book)
    service = RestatementService(shop_book)
    result = service.restate_certificate(
        certificate_id(shop_book), date(2024, 6, 12), "restated to the day of the test"
    )
    assert result.touched == 0
    assert "nothing was tested in the window" in result.describe()
    assert service.events.for_cylinder(KEY, standing_only=True)


def test_a_restatement_that_does_not_shorten_anything(shop_book: Book) -> None:
    service = RestatementService(shop_book)
    with pytest.raises(ConflictError, match="still stands"):
        service.restate_certificate(certificate_id(shop_book), date(2030, 1, 1), "wider")


def test_a_restatement_to_before_the_certificate_was_issued(shop_book: Book) -> None:
    service = RestatementService(shop_book)
    with pytest.raises(ConflictError, match="before it was issued"):
        service.restate_certificate(certificate_id(shop_book), date(2020, 1, 1), "way back")


def test_the_old_certificate_stays_in_the_book(shop_book: Book) -> None:
    service = RestatementService(shop_book)
    service.restate_certificate(certificate_id(shop_book), date(2026, 1, 1), "restated")
    standing = service.calibration.certificates(SYSTEM)
    everything = service.calibration.certificates(SYSTEM, standing_only=False)
    assert len(everything) == len(standing) + 1
    calibrated = [
        item for item in standing if item.instrument == InstrumentKind.CALIBRATED_CYLINDER
    ]
    assert calibrated[0].valid_until == date(2026, 1, 1)


def test_a_backwards_window_is_refused(shop_book: Book) -> None:
    with pytest.raises(ValidationError, match="ends after it starts"):
        RestatementService(shop_book).affected(SYSTEM, date(2024, 6, 12), date(2024, 6, 1))


def test_a_second_restatement_of_the_same_certificate(shop_book: Book) -> None:
    service = RestatementService(shop_book)
    first = certificate_id(shop_book)
    service.restate_certificate(first, date(2026, 1, 1), "restated")
    with pytest.raises(ConflictError, match="already superseded"):
        service.restate_certificate(first, date(2025, 1, 1), "again")
