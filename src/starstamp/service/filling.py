"""Recording a fill, and refusing the ones that should not happen.

The decision and the record are the same act here. A plant that logs the fill
and then checks whether it was allowed has already put the gas in, so the
check runs first and the log only ever holds fills the shop stands behind.

The one exception is a fill somebody insists on recording after the fact,
because it happened and the log is worth more complete than tidy. That takes
an explicit override and it is written down as one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.fillrecord import FillRecord
from starstamp.model.service import GasService
from starstamp.model.units import Pressure
from starstamp.rules.fill import FillDecision
from starstamp.rules.filling import FillJudgement, judge
from starstamp.service.fill import FillService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.facility import TechnicianRepository
from starstamp.store.fills import FillRepository

CITATION = "49 CFR 173.301"


@dataclass(frozen=True)
class FillOutcome:
    """What was recorded, and what the two rules said about it."""

    record: FillRecord
    decision: FillDecision
    judgement: FillJudgement
    overridden: bool = False

    def describe(self) -> str:
        line = self.record.describe()
        if self.overridden:
            line = f"{line}, recorded over a refusal"
        if not self.judgement.is_within:
            line = f"{line}, {self.judgement.describe()}"
        return line


class FillingService:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.cylinders = CylinderRepository(book.connection)
        self.fills = FillRepository(book.connection)
        self.technicians = TechnicianRepository(book.connection)
        self.eligibility = FillService(book)

    def record(
        self,
        key: CylinderKey,
        service: GasService,
        day: date,
        filler_badge: str,
        *,
        pressure: Pressure | None = None,
        weight_hundredths_lb: int | None = None,
        temperature_f: int = 70,
        note: str | None = None,
        override: bool = False,
    ) -> FillOutcome:
        cylinder = self.cylinders.by_key(key)
        filler = self.technicians.by_badge(filler_badge)
        decision = self.eligibility.decision(key, service, day)
        if not decision.allowed and not override:
            raise RuleViolationError(
                f"{key} may not be filled on {day.isoformat()}: " + "; ".join(decision.refusals),
                CITATION,
            )

        record = FillRecord(
            cylinder_key=str(key),
            service=service,
            filled_on=day,
            filler_badge=filler.badge,
            pressure=pressure,
            weight_hundredths_lb=weight_hundredths_lb,
            temperature_f=temperature_f,
            note=note,
        )
        last_pass = self.eligibility.events.latest_pass(key)
        plus = bool(last_pass and last_pass.plus_rated)
        judgement = judge(cylinder, record, plus=plus)
        written = self.fills.add(
            record,
            self.cylinders.id_of(key),
            judgement.verdict,
            judgement.settled,
            judgement.ceiling,
        )
        return FillOutcome(written, decision, judgement, overridden=not decision.allowed)

    def history(self, key: CylinderKey) -> list[FillRecord]:
        return self.fills.for_cylinder(key)

    def overfills(self, first: date, last: date) -> list[FillRecord]:
        return self.fills.overfills(first, last)
