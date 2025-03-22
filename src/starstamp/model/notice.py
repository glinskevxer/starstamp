"""What the shop has to tell the owner, and when it told them.

Condemning somebody else's property is the one thing a requalification shop
does that it cannot do quietly. The owner has to be told, in writing, and the
shop has to be able to show later that it was. A notice is therefore a record
in its own right rather than a flag on the condemnation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from starstamp.errors import ValidationError

NOTIFY_WITHIN_DAYS = 30


class NoticeKind(Enum):
    """Why the owner is being written to."""

    CONDEMNATION = "condemnation"
    DUE_SOON = "due_soon"
    OUT_OF_TEST = "out_of_test"
    HELD_FOR_REPAIR = "held_for_repair"
    UNCOLLECTED = "uncollected"

    @property
    def is_required(self) -> bool:
        """Whether the shop has to send it or merely wants to."""
        return self is NoticeKind.CONDEMNATION

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")


class NoticeState(Enum):
    DRAFTED = "drafted"
    SENT = "sent"

    @property
    def is_sent(self) -> bool:
        return self is NoticeState.SENT


@dataclass(frozen=True)
class Notice:
    """One letter to one account about one cylinder."""

    owner_code: str
    cylinder_key: str
    kind: NoticeKind
    raised_on: date
    body: str
    state: NoticeState = NoticeState.DRAFTED
    sent_on: date | None = None
    event_id: int | None = None
    notice_id: int | None = None

    def __post_init__(self) -> None:
        if not self.body.strip():
            raise ValidationError("a notice with nothing in it is not a notice")
        if (self.sent_on is None) == self.state.is_sent:
            raise ValidationError("a notice's state and its sending date have to agree")
        if self.sent_on is not None and self.sent_on < self.raised_on:
            raise ValidationError("a notice cannot go out before it was drafted")
        if self.kind is NoticeKind.CONDEMNATION and self.event_id is None:
            raise ValidationError("a condemnation notice has to name the record of test")

    def due_by(self) -> date | None:
        """The day the shop has to have sent it by, where there is one."""
        if not self.kind.is_required:
            return None
        return self.raised_on + timedelta(days=NOTIFY_WITHIN_DAYS)

    def is_late(self, today: date) -> bool:
        deadline = self.due_by()
        if deadline is None or self.state.is_sent:
            return False
        return today > deadline

    def days_left(self, today: date) -> int | None:
        deadline = self.due_by()
        if deadline is None:
            return None
        return (deadline - today).days

    def summary(self) -> str:
        head = (
            f"{self.raised_on.isoformat()} {self.owner_code} {self.cylinder_key} {self.kind.label}"
        )
        if self.state.is_sent:
            return f"{head}, sent {self.sent_on}"
        return f"{head}, not sent"
