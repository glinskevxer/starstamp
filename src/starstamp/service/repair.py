"""Booking a repair, and working out what it leaves the cylinder needing.

A repair on its own never puts a cylinder back in service. Either it clears a
suspension, in which case the requalification that was interrupted still has
to be finished, or it touched the pressure envelope, in which case the
cylinder needs a fresh test whatever its due date says. The one case where a
repair leaves the cylinder where it found it is ordinary work on a cylinder
that was not held for anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import RuleViolationError, ValidationError
from starstamp.model.cylinder import Cylinder, CylinderKey, CylinderStatus
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.repair import Repair, RepairKind
from starstamp.model.valve import Outlet, parse_outlet
from starstamp.rules.repair import clears_a_suspension, require_permitted
from starstamp.rules.valve import required_outlet
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.facility import FacilityRepository, TechnicianRepository
from starstamp.store.repairs import RepairRepository

CITATION = "49 CFR 180.211"


def outlet_in(parts: str) -> Outlet | None:
    """Find a CGA number anywhere in a parts line.

    A number the shop does not stock reads as no outlet at all rather than as
    an error, so the caller can say what it wants about the whole parts line
    instead of about one token in it.
    """
    for token in parts.replace(",", " ").split():
        cleaned = token.strip().upper().removeprefix("CGA")
        if cleaned.isdigit():
            try:
                return parse_outlet(cleaned)
            except ValidationError:
                return None
    return None


@dataclass(frozen=True)
class RepairOutcome:
    """The repair, and what it leaves the cylinder needing."""

    repair: Repair
    cleared: RequalificationEvent | None
    status_after: CylinderStatus
    needs_requalification: bool

    def describe(self) -> str:
        line = self.repair.summary()
        if self.cleared is not None:
            line = f"{line}, clears the hold from {self.cleared.performed_on.isoformat()}"
        if self.needs_requalification:
            line = f"{line}, requalify before filling"
        return line


class RepairService:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.cylinders = CylinderRepository(book.connection)
        self.repairs = RepairRepository(book.connection)
        self.events = EventRepository(book.connection)
        self.technicians = TechnicianRepository(book.connection)
        self.facilities = FacilityRepository(book.connection)

    def held_by(self, key: CylinderKey) -> RequalificationEvent | None:
        """The standing suspension a cylinder is sitting under, if any."""
        for event in reversed(self.events.for_cylinder(key, standing_only=True)):
            if event.outcome is Outcome.SUSPENDED:
                return event
            if event.outcome is Outcome.PASS:
                return None
        return None

    def perform(
        self,
        key: CylinderKey,
        kind: RepairKind,
        day: date,
        technician_badge: str,
        *,
        parts: str | None = None,
        note: str | None = None,
        facility_rin: str | None = None,
    ) -> RepairOutcome:
        cylinder = self.cylinders.by_key(key)
        require_permitted(cylinder, kind, day)
        technician = self.technicians.by_badge(technician_badge)
        rin = facility_rin
        if kind.touches_the_pressure_envelope and rin is None:
            rin = self.facilities.only().rin
        if rin is not None:
            facility = self.facilities.by_rin(rin)
            if not facility.approved_on(day):
                raise RuleViolationError(
                    f"{facility.rin} was not in force on {day.isoformat()}", CITATION
                )

        if kind is RepairKind.VALVE_REPLACEMENT:
            self._fit_valve(cylinder, parts or "", day)

        held = self.held_by(key)
        cleared = held if held is not None and clears_a_suspension(kind) else None
        repair = Repair(
            cylinder_key=str(key),
            kind=kind,
            performed_on=day,
            technician_badge=technician.badge,
            facility_rin=rin,
            parts=parts,
            note=note,
        )
        written = self.repairs.add(
            repair,
            self.cylinders.id_of(key),
            clears_event_id=None if cleared is None else cleared.event_id,
        )

        needs_test = kind.needs_a_requalification_after or cleared is not None
        status = self._settle_status(cylinder.status, cleared is not None, needs_test)
        if status is not cylinder.status:
            self.cylinders.set_status(key, status)
        return RepairOutcome(written, cleared, status, needs_test)

    def _fit_valve(self, cylinder: Cylinder, parts: str, day: date) -> None:
        """Read the outlet off the parts line and put it on the cylinder.

        A valve change is the one repair that changes what the filling plant
        is allowed to do, so the outlet is not left in a free text field where
        nothing can read it.
        """
        outlet = outlet_in(parts)
        if outlet is None:
            raise RuleViolationError(
                f"a valve change has to name the outlet fitted, as in CGA 580, not {parts!r}",
                CITATION,
            )
        wanted = required_outlet(cylinder.service)
        if outlet.number != wanted.number:
            raise RuleViolationError(
                f"{cylinder.key} is in {cylinder.service} service and takes {wanted}, "
                f"not {outlet}; change the service first if that is the intention",
                CITATION,
            )
        self.cylinders.fit_valve(cylinder.key, outlet.number, day)

    def _settle_status(
        self, current: CylinderStatus, cleared: bool, needs_test: bool
    ) -> CylinderStatus:
        if cleared or needs_test:
            return CylinderStatus.IN_SHOP
        return current

    def history(self, key: CylinderKey) -> list[Repair]:
        return self.repairs.for_cylinder(key)
