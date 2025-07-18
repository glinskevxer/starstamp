"""Re-marking a cylinder whose stamping has worn away.

The service's whole job is to put the evidence in front of the rule before
anything is stamped. That evidence is the book's own history, which is why
this cannot be done from the model alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.marking import Evidence, MarkKind, Remarking, RestoredMark
from starstamp.rules.remarking import CITATION, check, supporting_records
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.facility import FacilityRepository, TechnicianRepository
from starstamp.store.markings import RemarkingRepository


@dataclass(frozen=True)
class RemarkOutcome:
    """What was stamped, and what it rested on."""

    remarking: Remarking
    supporting_records: int

    def describe(self) -> str:
        line = self.remarking.summary()
        if self.remarking.evidence.is_ours:
            return f"{line}, on {self.supporting_records} records of ours"
        return line


class RemarkService:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.cylinders = CylinderRepository(book.connection)
        self.events = EventRepository(book.connection)
        self.markings = RemarkingRepository(book.connection)
        self.facilities = FacilityRepository(book.connection)
        self.technicians = TechnicianRepository(book.connection)

    def restore(
        self,
        key: CylinderKey,
        marks: tuple[RestoredMark, ...],
        evidence: Evidence,
        day: date,
        technician_badge: str,
        *,
        facility_rin: str | None = None,
        note: str | None = None,
    ) -> RemarkOutcome:
        cylinder = self.cylinders.by_key(key)
        technician = self.technicians.by_badge(technician_badge)
        facility = self.facilities.by_rin(facility_rin) if facility_rin else self.facilities.only()
        if not facility.approved_on(day):
            raise RuleViolationError(
                f"{facility.rin} was not in force on {day.isoformat()}", CITATION
            )

        history = self.events.for_cylinder(key)
        check(cylinder, marks, evidence, history, day).require()
        remarking = Remarking(
            cylinder_key=str(key),
            marked_on=day,
            facility_rin=facility.rin,
            technician_badge=technician.badge,
            evidence=evidence,
            marks=marks,
            note=note,
        )
        written = self.markings.add(remarking, self.cylinders.id_of(key))
        return RemarkOutcome(written, len(supporting_records(history)))

    def history(self, key: CylinderKey) -> list[Remarking]:
        return self.markings.for_cylinder(key)

    def what_we_could_restore(self, key: CylinderKey) -> dict[MarkKind, str]:
        """The marks the book could stand behind for this cylinder."""
        cylinder = self.cylinders.by_key(key)
        found: dict[MarkKind, str] = {
            MarkKind.SERIAL: cylinder.key.serial,
            MarkKind.MANUFACTURER: cylinder.key.manufacturer_symbol,
            MarkKind.SPECIFICATION: str(cylinder.specification),
            MarkKind.MANUFACTURE_DATE: str(cylinder.manufactured),
        }
        pressure = cylinder.specification.service_pressure
        if pressure is not None:
            found[MarkKind.SERVICE_PRESSURE] = str(pressure.psig)
        if cylinder.rejection_elastic_expansion is not None:
            found[MarkKind.REJECTION_LIMIT] = str(
                cylinder.rejection_elastic_expansion
            ).removesuffix(" cc")
        if cylinder.tare_hundredths_lb is not None:
            found[MarkKind.TARE_WEIGHT] = f"TW {cylinder.tare_hundredths_lb / 100:.1f}"
        return found
