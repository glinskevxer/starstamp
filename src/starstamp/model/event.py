"""A requalification, as it goes into the record.

The event is what an auditor reads. It carries the cylinder, the day, the
method, who did it under whose number, what the rig read, what the inspector
found, and the verdict that came out of all of it. It also carries whether it
still stands, because the one thing a record of test must never do is change
after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum

from starstamp.errors import ValidationError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.model.method import Method
from starstamp.model.testrecord import PressureReadings


class Outcome(Enum):
    """What the shop did with the cylinder at the end of the event."""

    PASS = "pass"
    CONDEMN = "condemn"
    SUSPENDED = "suspended"

    @property
    def may_be_marked(self) -> bool:
        """Only a pass earns a stamp."""
        return self is Outcome.PASS


class EventState(Enum):
    """Whether the event still stands.

    A record is never edited and never deleted. When the ground it rested on
    turns out to have moved, it is reversed and a replacement is written
    beside it, and both stay in the book.
    """

    RECORDED = "recorded"
    REVERSED = "reversed"
    REPLACEMENT = "replacement"

    @property
    def stands(self) -> bool:
        return self is not EventState.REVERSED


@dataclass(frozen=True)
class RequalificationEvent:
    """One pass across the bench."""

    cylinder: CylinderKey
    performed_on: date
    method: Method
    facility_rin: str
    technician_badge: str
    outcome: Outcome
    reasons: tuple[str, ...] = ()
    system_code: str | None = None
    readings: PressureReadings | None = None
    wall_thousandths_in: int | None = None
    state: EventState = EventState.RECORDED
    reverses: int | None = None
    event_id: int | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.method.is_pressure_test and self.readings is None:
            raise ValidationError(f"{self.method.label} has to carry the rig's readings")
        if not self.method.is_pressure_test and self.readings is not None:
            raise ValidationError(f"{self.method.label} never put the cylinder on a rig")
        if self.method.needs_water_jacket and self.system_code is None:
            raise ValidationError(f"{self.method.label} has to name the test system")
        if self.outcome is Outcome.CONDEMN and not self.reasons:
            raise ValidationError("a condemnation has to say why")
        if self.state is EventState.REPLACEMENT and self.reverses is None:
            raise ValidationError("a replacement has to name the event it replaces")
        if self.state is not EventState.REPLACEMENT and self.reverses is not None:
            raise ValidationError("only a replacement names an event it replaces")

    @property
    def marked_month(self) -> StampedMonth:
        """The month that would be stamped for this event."""
        return StampedMonth.of(self.performed_on)

    @property
    def may_be_marked(self) -> bool:
        return self.outcome.may_be_marked and self.state.stands

    @property
    def is_condemnation(self) -> bool:
        return self.outcome is Outcome.CONDEMN and self.state.stands

    def with_id(self, event_id: int) -> RequalificationEvent:
        return replace(self, event_id=event_id)

    def reversed_by(self, reason: str) -> RequalificationEvent:
        if self.state is EventState.REVERSED:
            raise ValidationError("that event has already been reversed")
        return replace(self, state=EventState.REVERSED, notes=(*self.notes, reason))

    def summary(self) -> str:
        head = (
            f"{self.performed_on.isoformat()} {self.cylinder} {self.method.label} "
            f"{self.outcome.value}"
        )
        if self.state is not EventState.RECORDED:
            head = f"{head} [{self.state.value}]"
        if self.reasons:
            head = f"{head}: " + "; ".join(self.reasons)
        return head
