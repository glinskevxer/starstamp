"""Putting a cylinder through requalification.

This is the only place that knows the order. Every rule it calls is pure and
tested on its own; what is worth reading here is which answer feeds which
question, because that is where a shop gets it wrong.

    the cylinder and the gas          say which methods exist
    the RIN and the badge             narrow those to what may be performed
    the certificates and the check    say whether the readings will count
    the visual inspection             says whether the cylinder reaches the rig
    the rig                           says whether it passed
    all of the above together         say whether it earns a star

A refusal at any point before the visual means no event is written at all,
because nothing happened that is worth recording. From the visual onwards an
event is always written, including the ones that condemn.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import RuleViolationError
from starstamp.model.acetylene import AcetyleneExam
from starstamp.model.cylinder import Cylinder, CylinderKey, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import Observation
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.method import Method
from starstamp.model.testrecord import PressureReadings
from starstamp.model.ultrasonic import Scan
from starstamp.rules import validity as validity_rules
from starstamp.rules.acetylene import AcetyleneOutcome
from starstamp.rules.acetylene import evaluate as evaluate_acetylene
from starstamp.rules.authorisation import authorise, choose_method
from starstamp.rules.interval import due_month, life_expired
from starstamp.rules.marks import Eligibility, plus_eligibility, star_eligibility
from starstamp.rules.pressure_test import PressureOutcome, evaluate
from starstamp.rules.ultrasonic import ScanOutcome
from starstamp.rules.ultrasonic import evaluate as evaluate_scan
from starstamp.rules.visual import VisualAssessment, VisualResult
from starstamp.rules.visual import assess as assess_visual
from starstamp.service.receiving import ReceivingService
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.facility import FacilityRepository, TechnicianRepository

CITATION = "49 CFR 180.205"


@dataclass(frozen=True)
class RequalificationRequest:
    """Everything the bench hands in for one cylinder."""

    key: CylinderKey
    day: date
    technician_badge: str
    method: Method | None = None
    system_code: str | None = None
    observations: tuple[Observation, ...] = ()
    readings: PressureReadings | None = None
    scan: Scan | None = None
    acetylene: AcetyleneExam | None = None
    facility_rin: str | None = None


@dataclass(frozen=True)
class RequalificationResult:
    """The event that was written, and everything that produced it."""

    event: RequalificationEvent
    visual: VisualAssessment
    validity: validity_rules.Validity
    pressure: PressureOutcome | None
    scan: ScanOutcome | None
    acetylene: AcetyleneOutcome | None
    star: Eligibility
    plus: Eligibility
    due: StampedMonth | None

    @property
    def outcome(self) -> Outcome:
        return self.event.outcome

    def summary(self) -> str:
        line = self.event.summary()
        if self.due is not None:
            line = f"{line}, due {self.due}"
        if self.star.granted:
            line = f"{line}, starred"
        if self.plus.granted:
            line = f"{line}, plus"
        return line


class RequalificationService:
    """The bench's one entry point."""

    def __init__(self, book: Book) -> None:
        self.book = book
        self.cylinders = CylinderRepository(book.connection)
        self.events = EventRepository(book.connection)
        self.facilities = FacilityRepository(book.connection)
        self.technicians = TechnicianRepository(book.connection)
        self.calibration = CalibrationRepository(book.connection)

    def perform(self, request: RequalificationRequest) -> RequalificationResult:
        cylinder = self.cylinders.by_key(request.key)
        facility = (
            self.facilities.by_rin(request.facility_rin)
            if request.facility_rin
            else self.facilities.only()
        )
        technician = self.technicians.by_badge(request.technician_badge)

        if life_expired(cylinder, request.day):
            raise RuleViolationError(
                f"{cylinder.key} is past the service life of its specification", CITATION
            )

        method = request.method or choose_method(cylinder, facility, technician, request.day)
        authorise(cylinder, facility, technician, method, request.day)

        system_code = request.system_code or ""
        certificates = self.calibration.certificates(system_code) if system_code else []
        check = self.calibration.check_on(system_code, request.day) if system_code else None
        validity = validity_rules.assess(
            method, request.day, system_code, certificates, check
        ).require()

        visual = assess_visual(
            list(request.observations),
            cylinder.specification,
            cylinder.service,
            cylinder.nominal_wall_thousandths_in or 0,
        )
        pressure = self._run_rig(cylinder, method, request, visual)
        scan = self._run_scan(cylinder, method, request, visual)
        acetylene = self._weigh(cylinder, method, request, visual)
        outcome, reasons = self._decide(visual, pressure, scan, acetylene)

        star = star_eligibility(
            cylinder,
            method,
            request.readings,
            pressure,
            visual,
            previous_due=self._previous_due(cylinder),
            day=request.day,
        )
        plus = plus_eligibility(cylinder, method, request.readings, pressure, visual)

        event = RequalificationEvent(
            cylinder=cylinder.key,
            performed_on=request.day,
            method=method,
            facility_rin=facility.rin,
            technician_badge=technician.badge,
            outcome=outcome,
            reasons=reasons,
            system_code=request.system_code,
            readings=request.readings if method.is_pressure_test else None,
            wall_thousandths_in=cylinder.nominal_wall_thousandths_in,
            starred=star.granted and outcome is Outcome.PASS,
            plus_rated=plus.granted and outcome is Outcome.PASS,
            star_refused=star.refusals,
            plus_refused=plus.refusals,
        )
        written = self.events.add(event, self.cylinders.id_of(cylinder.key), list(visual.findings))
        if request.scan is not None and written.event_id is not None:
            self.events.add_scan(written.event_id, request.scan)
        if request.acetylene is not None and written.event_id is not None:
            self.events.add_acetylene_exam(
                written.event_id, request.acetylene, cylinder.tare_hundredths_lb or 0
            )
        self._move_cylinder(cylinder, outcome)
        ReceivingService(self.book).settle_from_event(written)

        due = (
            due_month(cylinder, written.marked_month, method, starred=star.granted)
            if outcome is Outcome.PASS
            else None
        )
        return RequalificationResult(
            written, visual, validity, pressure, scan, acetylene, star, plus, due
        )

    def _run_rig(
        self,
        cylinder: Cylinder,
        method: Method,
        request: RequalificationRequest,
        visual: VisualAssessment,
    ) -> PressureOutcome | None:
        """A cylinder that failed its visual never goes on the rig."""
        if visual.result is not VisualResult.PASS:
            return None
        if not method.is_pressure_test:
            return None
        if request.readings is None:
            raise RuleViolationError(
                f"{method.label} needs the rig's readings before an event can be written",
                CITATION,
            )
        return evaluate(cylinder, method, request.readings)

    def _run_scan(
        self,
        cylinder: Cylinder,
        method: Method,
        request: RequalificationRequest,
        visual: VisualAssessment,
    ) -> ScanOutcome | None:
        """An ultrasonic exam, on a cylinder that got past its visual."""
        if method is not Method.ULTRASONIC:
            if request.scan is not None:
                raise RuleViolationError(f"{method.label} takes no ultrasonic readings", CITATION)
            return None
        if visual.result is not VisualResult.PASS:
            return None
        if request.scan is None:
            raise RuleViolationError(
                "an ultrasonic examination needs its readings before an event can be written",
                CITATION,
            )
        return evaluate_scan(cylinder, request.scan)

    def _weigh(
        self,
        cylinder: Cylinder,
        method: Method,
        request: RequalificationRequest,
        visual: VisualAssessment,
    ) -> AcetyleneOutcome | None:
        """The weighing that stands in for a rig on an acetylene cylinder."""
        if method is not Method.ACETYLENE_VISUAL:
            if request.acetylene is not None:
                raise RuleViolationError(f"{method.label} does not weigh the cylinder", CITATION)
            return None
        if visual.result is not VisualResult.PASS:
            return None
        if request.acetylene is None:
            raise RuleViolationError(
                "an acetylene examination needs the cylinder weighed before an event "
                "can be written",
                CITATION,
            )
        return evaluate_acetylene(cylinder, request.acetylene)

    def _decide(
        self,
        visual: VisualAssessment,
        pressure: PressureOutcome | None,
        scan: ScanOutcome | None = None,
        acetylene: AcetyleneOutcome | None = None,
    ) -> tuple[Outcome, tuple[str, ...]]:
        if visual.result is VisualResult.CONDEMN:
            return Outcome.CONDEMN, tuple(
                finding.observation.describe() for finding in visual.condemning()
            )
        if visual.result is VisualResult.REPAIR:
            return Outcome.SUSPENDED, tuple(
                f"{finding.observation.describe()} has to be put right"
                for finding in visual.findings
                if finding.result is VisualResult.REPAIR
            )
        if pressure is not None and not pressure.passed:
            return Outcome.CONDEMN, pressure.reasons
        if scan is not None and not scan.passed:
            return Outcome.CONDEMN, scan.reasons
        if acetylene is not None and not acetylene.passed:
            if acetylene.result is VisualResult.REPAIR:
                return Outcome.SUSPENDED, acetylene.reasons
            return Outcome.CONDEMN, acetylene.reasons
        return Outcome.PASS, ()

    def _previous_due(self, cylinder: Cylinder) -> StampedMonth | None:
        previous = self.events.latest_pass(cylinder.key)
        if previous is None:
            return None
        return due_month(cylinder, previous.marked_month, previous.method)

    def _move_cylinder(self, cylinder: Cylinder, outcome: Outcome) -> None:
        if outcome is Outcome.CONDEMN:
            self.cylinders.set_status(cylinder.key, CylinderStatus.CONDEMNED)
        elif outcome is Outcome.SUSPENDED:
            self.cylinders.set_status(cylinder.key, CylinderStatus.AWAITING_REPAIR)
        elif cylinder.status is not CylinderStatus.IN_SERVICE:
            self.cylinders.set_status(cylinder.key, CylinderStatus.IN_SERVICE)
