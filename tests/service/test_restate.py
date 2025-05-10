from datetime import date

import pytest

from starstamp.errors import ConflictError, ValidationError
from starstamp.model.calibration import InstrumentKind
from starstamp.model.cylinder import CylinderKey
from starstamp.model.event import EventState, Outcome
from starstamp.model.service import NITROGEN
from starstamp.service.fill import FillService
from starstamp.service.restate import RestatementService
from starstamp.store.db import Book

from ..support.requests import requalify
from ..support.shop import SYSTEM

KEY = CylinderKey("NCI", "A4471")


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


def test_a_typed_reading_is_corrected_not_edited(shop_book: Book) -> None:
    from starstamp.model.testrecord import PressureReadings
    from starstamp.model.units import Expansion, Pressure
    from starstamp.service.restate import CorrectionService

    requalify(shop_book)
    service = CorrectionService(shop_book)
    corrected = service.correct(
        1,
        "the total was typed from the wrong line of the strip",
        readings=PressureReadings(
            applied=Pressure(3358),
            hold_seconds=30,
            total_expansion=Expansion.parse("112.0"),
            permanent_expansion=Expansion.parse("2.0"),
        ),
    )
    assert corrected.reversed_id == 1
    assert "total 110.0 cc to 112.0 cc" in corrected.describe()
    history = service.events.for_cylinder(KEY)
    assert [event.state.value for event in history] == ["reversed", "replacement"]
    assert history[1].readings is not None
    assert history[1].readings.total == Expansion.parse("112.0")


def test_a_correction_that_changes_nothing(shop_book: Book) -> None:
    from starstamp.service.restate import CorrectionService

    requalify(shop_book)
    service = CorrectionService(shop_book)
    with pytest.raises(ConflictError, match="nothing in that correction"):
        service.correct(1, "no change", system_code="WJ-1")


def test_a_correction_needs_something_to_change(shop_book: Book) -> None:
    from starstamp.errors import ValidationError
    from starstamp.service.restate import CorrectionService

    requalify(shop_book)
    with pytest.raises(ValidationError, match="has to change something"):
        CorrectionService(shop_book).correct(1, "no change")


def test_a_reversed_record_cannot_be_corrected(shop_book: Book) -> None:
    from starstamp.errors import NotFoundError
    from starstamp.service.restate import CorrectionService

    requalify(shop_book)
    service = CorrectionService(shop_book)
    service.events.reverse(1, "already pulled")
    with pytest.raises(NotFoundError, match="has been reversed"):
        service.correct(1, "too late", technician_badge="MR2")


def test_the_correction_keeps_the_marks(shop_book: Book) -> None:
    from starstamp.service.restate import CorrectionService
    from starstamp.store.facility import TechnicianRepository

    from ..support.factories import make_technician

    requalify(shop_book)
    TechnicianRepository(shop_book.connection).add(
        make_technician(badge="MR2", name="Marisol Reyes")
    )
    corrected = CorrectionService(shop_book).correct(
        1, "wrong badge on the sheet", technician_badge="MR2"
    )
    assert corrected.replacement.starred
    assert corrected.replacement.technician_badge == "MR2"


def test_a_correction_normalises_the_badge(shop_book: Book) -> None:
    from starstamp.errors import NotFoundError
    from starstamp.service.restate import CorrectionService

    requalify(shop_book)
    service = CorrectionService(shop_book)
    with pytest.raises(ConflictError, match="nothing in that correction"):
        service.correct(1, "same person", technician_badge="jt7")
    with pytest.raises(NotFoundError, match="no technician ZZ9"):
        service.correct(1, "nobody", technician_badge="zz9")
