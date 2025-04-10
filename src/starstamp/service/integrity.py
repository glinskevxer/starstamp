"""Reading a whole book looking for things that cannot all be true at once.

Every one of these has happened somewhere. A cylinder condemned in March and
requalified in April, because two people were working from different lists. A
record of test with no certificate behind it, because the certificate was
filed under the wrong rig. A condemnation nobody wrote to the owner about.

Nothing here fixes anything. The point is to find the disagreement and name
both sides of it, so that a person decides which one is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from starstamp.errors import NotFoundError
from starstamp.model.cylinder import Cylinder, CylinderKey, CylinderStatus
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.rules.validity import required_instruments
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.facility import TechnicianRepository
from starstamp.store.lots import LotRepository
from starstamp.store.migrations import discover, schema_version
from starstamp.store.notices import NoticeRepository


class Severity(Enum):
    """How much the disagreement matters."""

    WARNING = "warning"
    PROBLEM = "problem"

    @property
    def is_problem(self) -> bool:
        return self is Severity.PROBLEM


@dataclass(frozen=True)
class Finding:
    """One thing that does not add up."""

    check: str
    severity: Severity
    subject: str
    detail: str

    def __str__(self) -> str:
        return f"{self.severity.value}: {self.check}: {self.subject}: {self.detail}"


@dataclass(frozen=True)
class Report:
    findings: tuple[Finding, ...]
    checked: int

    @property
    def problems(self) -> tuple[Finding, ...]:
        return tuple(item for item in self.findings if item.severity.is_problem)

    @property
    def is_clean(self) -> bool:
        return not self.findings

    def describe(self) -> str:
        if self.is_clean:
            return f"{self.checked} cylinders checked, nothing to answer for"
        lines = [
            f"{self.checked} cylinders checked, {len(self.problems)} problems, "
            f"{len(self.findings) - len(self.problems)} warnings"
        ]
        lines.extend(f"  {finding}" for finding in self.findings)
        return "\n".join(lines)


class IntegrityService:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.cylinders = CylinderRepository(book.connection)
        self.events = EventRepository(book.connection)
        self.calibration = CalibrationRepository(book.connection)
        self.notices = NoticeRepository(book.connection)
        self.lots = LotRepository(book.connection)
        self.technicians = TechnicianRepository(book.connection)

    def run(self, today: date) -> Report:
        findings: list[Finding] = []
        findings.extend(self._schema())
        fleet = [
            cylinder for status in CylinderStatus for cylinder in self.cylinders.with_status(status)
        ]
        for cylinder in fleet:
            history = self.events.for_cylinder(cylinder.key, standing_only=True)
            findings.extend(self._work_after_condemnation(cylinder.key, history))
            findings.extend(self._status_against_history(cylinder, history))
            findings.extend(self._evidence(history))
            findings.extend(self._notices(cylinder.owner_code, history))
            findings.extend(self._signed_off(history))
        findings.extend(self._settled_against_reversals())
        findings.extend(self._late_letters(today))
        findings.extend(self._undealt_with(today))
        return Report(tuple(findings), len(fleet))

    def _schema(self) -> list[Finding]:
        expected = len(discover())
        found = schema_version(self.book.connection)
        if found == expected:
            return []
        return [
            Finding(
                "schema",
                Severity.PROBLEM,
                "book",
                f"schema is at {found} and the code ships {expected} migrations",
            )
        ]

    def _work_after_condemnation(
        self, key: CylinderKey, history: list[RequalificationEvent]
    ) -> list[Finding]:
        condemned_on: date | None = None
        findings: list[Finding] = []
        for event in history:
            if condemned_on is not None and event.outcome is Outcome.PASS:
                findings.append(
                    Finding(
                        "work after condemnation",
                        Severity.PROBLEM,
                        str(key),
                        f"passed on {event.performed_on.isoformat()} after being condemned on "
                        f"{condemned_on.isoformat()}",
                    )
                )
            if event.outcome is Outcome.CONDEMN:
                condemned_on = event.performed_on
        return findings

    def _status_against_history(
        self, cylinder: Cylinder, history: list[RequalificationEvent]
    ) -> list[Finding]:
        condemned = any(event.outcome is Outcome.CONDEMN for event in history)
        if condemned and cylinder.status not in {
            CylinderStatus.CONDEMNED,
            CylinderStatus.SCRAPPED,
        }:
            return [
                Finding(
                    "status against history",
                    Severity.PROBLEM,
                    str(cylinder.key),
                    f"was condemned but reads {cylinder.status.value}",
                )
            ]
        if not condemned and cylinder.status is CylinderStatus.CONDEMNED:
            return [
                Finding(
                    "status against history",
                    Severity.WARNING,
                    str(cylinder.key),
                    "reads condemned with no condemning record of test",
                )
            ]
        return []

    def _evidence(self, history: list[RequalificationEvent]) -> list[Finding]:
        findings: list[Finding] = []
        for event in history:
            if not event.method.is_pressure_test or not event.system_code:
                continue
            held = {
                certificate.instrument
                for certificate in self.calibration.in_force(event.system_code, event.performed_on)
            }
            missing = sorted(required_instruments(event.method) - held)
            if missing:
                findings.append(
                    Finding(
                        "evidence",
                        Severity.PROBLEM,
                        f"record {event.event_id}",
                        f"{event.system_code} on {event.performed_on.isoformat()} has no "
                        + ", ".join(missing)
                        + " certificate on file",
                    )
                )
        return findings

    def _notices(self, owner_code: str, history: list[RequalificationEvent]) -> list[Finding]:
        findings: list[Finding] = []
        for event in history:
            if event.outcome is not Outcome.CONDEMN or event.event_id is None:
                continue
            if not self.notices.for_event(event.event_id):
                findings.append(
                    Finding(
                        "notices",
                        Severity.WARNING,
                        f"record {event.event_id}",
                        f"{owner_code} has not been written to about this condemnation",
                    )
                )
        return findings

    def _late_letters(self, today: date) -> list[Finding]:
        """Condemnation letters past the day they had to be sent by."""
        return [
            Finding(
                "notices",
                Severity.PROBLEM,
                f"notice {notice.notice_id}",
                f"{notice.owner_code} should have been written to by "
                f"{notice.due_by()} about {notice.cylinder_key}",
            )
            for notice in self.notices.unsent()
            if notice.is_late(today)
        ]

    def _undealt_with(self, today: date) -> list[Finding]:
        """Condemned cylinders still sitting on the floor past the deadline."""
        from starstamp.service.disposal import DisposalService

        return [
            Finding(
                "disposal",
                Severity.PROBLEM,
                str(row.cylinder.key),
                f"condemned {row.condemned_on.isoformat()} and not rendered; it was due by "
                f"{row.due_by.isoformat()}",
            )
            for row in DisposalService(self.book).late(today)
        ]

    def _signed_off(self, history: list[RequalificationEvent]) -> list[Finding]:
        """Work recorded against a badge that was not signed off that day.

        This is the check that reads the past rather than the present. A
        technician whose sign off lapsed in March is fine today and every test
        they did in April is not, and nothing else in the book would say so.
        """
        findings: list[Finding] = []
        for event in history:
            try:
                technician = self.technicians.by_badge(event.technician_badge)
            except NotFoundError:
                findings.append(
                    Finding(
                        "sign off",
                        Severity.WARNING,
                        f"record {event.event_id}",
                        f"{event.technician_badge} is not on the bench",
                    )
                )
                continue
            if not technician.may_perform(event.method, event.performed_on):
                findings.append(
                    Finding(
                        "sign off",
                        Severity.PROBLEM,
                        f"record {event.event_id}",
                        f"{technician.badge} was not signed off for {event.method.label} on "
                        f"{event.performed_on.isoformat()}",
                    )
                )
        return findings

    def _settled_against_reversals(self) -> list[Finding]:
        findings: list[Finding] = []
        for lot in self.lots.open_lots():
            for line in self.lots.lines(lot.number):
                if line.event_id is None:
                    continue
                event = self.events.by_id(line.event_id)
                if not event.state.stands:
                    findings.append(
                        Finding(
                            "lot lines",
                            Severity.PROBLEM,
                            f"{lot.number} {line.cylinder_key}",
                            f"settled against record {line.event_id}, which was reversed",
                        )
                    )
        return findings
