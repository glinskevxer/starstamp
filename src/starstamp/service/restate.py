"""What happens when the ground a record of test rested on turns out to move.

A calibration house restates a certificate perhaps once every few years, and
when it does, every requalification the rig performed inside the window that
lost cover stops being a requalification. The readings were real and the
cylinders may well be sound, but the shop can no longer say so, and the only
honest thing it can do is say that too.

Nothing is edited. Each affected record is reversed, and a replacement is
written beside it carrying the reason and no verdict the shop cannot support.
An auditor reading the book afterwards sees both, in order, with the
restatement between them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from starstamp.errors import ConflictError, ValidationError
from starstamp.model.calibration import Certificate
from starstamp.model.event import EventState, Outcome, RequalificationEvent
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository


@dataclass(frozen=True)
class Restatement:
    """What a restatement did, in the order it did it."""

    certificate: Certificate
    corrected_until: date
    window: tuple[date, date]
    reversed_ids: tuple[int, ...]
    replacements: tuple[RequalificationEvent, ...]

    @property
    def touched(self) -> int:
        return len(self.reversed_ids)

    def describe(self) -> str:
        first, last = self.window
        if not self.reversed_ids:
            return (
                f"{self.certificate.instrument} on {self.certificate.system_code} restated to "
                f"{self.corrected_until.isoformat()}, nothing was tested in the window"
            )
        return (
            f"{self.certificate.instrument} on {self.certificate.system_code} restated to "
            f"{self.corrected_until.isoformat()}, {self.touched} records between "
            f"{first.isoformat()} and {last.isoformat()} reversed"
        )


class RestatementService:
    """Pulling a window of work after a certificate is restated."""

    def __init__(self, book: Book) -> None:
        self.book = book
        self.calibration = CalibrationRepository(book.connection)
        self.events = EventRepository(book.connection)
        self.cylinders = CylinderRepository(book.connection)

    def affected(self, system_code: str, first: date, last: date) -> list[RequalificationEvent]:
        """The standing records a window covers."""
        if last < first:
            raise ValidationError("a restatement window ends after it starts")
        return [
            event
            for event in self.events.for_system_between(system_code, first, last)
            if event.state.stands
        ]

    def restate_certificate(
        self, certificate_id: int, corrected_until: date, reason: str
    ) -> Restatement:
        """Shorten a certificate and pull everything it no longer covers."""
        certificate = self.calibration.by_id(certificate_id)
        if corrected_until >= certificate.valid_until:
            raise ConflictError(
                "a restatement that does not shorten the certificate changes nothing; "
                f"{certificate.valid_until.isoformat()} still stands"
            )
        if corrected_until < certificate.issued_on:
            raise ConflictError("a certificate cannot be restated to before it was issued")

        window = (corrected_until + timedelta(days=1), certificate.valid_until)
        affected = self.affected(certificate.system_code, *window)

        self.calibration.supersede(certificate_id, reason)
        self.calibration.add_certificate(
            Certificate(
                system_code=certificate.system_code,
                instrument=certificate.instrument,
                serial=certificate.serial,
                issued_on=certificate.issued_on,
                valid_until=corrected_until,
                issued_by=certificate.issued_by,
                standard=certificate.standard,
            ),
            note=reason,
        )

        reversed_ids: list[int] = []
        replacements: list[RequalificationEvent] = []
        for event in affected:
            if event.event_id is None:
                continue
            self.events.reverse(event.event_id, reason)
            replacement = RequalificationEvent(
                cylinder=event.cylinder,
                performed_on=event.performed_on,
                method=event.method,
                facility_rin=event.facility_rin,
                technician_badge=event.technician_badge,
                outcome=Outcome.SUSPENDED,
                reasons=(
                    f"the {certificate.instrument} certificate covering this test was restated "
                    f"to end {corrected_until.isoformat()}",
                ),
                system_code=event.system_code,
                readings=event.readings,
                wall_thousandths_in=event.wall_thousandths_in,
                state=EventState.REPLACEMENT,
                reverses=event.event_id,
            )
            written = self.events.add(replacement, self.cylinders.id_of(event.cylinder))
            replacements.append(written)
            reversed_ids.append(event.event_id)

        return Restatement(
            certificate=certificate,
            corrected_until=corrected_until,
            window=window,
            reversed_ids=tuple(reversed_ids),
            replacements=tuple(replacements),
        )
