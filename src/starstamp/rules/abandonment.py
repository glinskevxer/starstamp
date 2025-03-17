"""Cylinders nobody has come back for.

Every shop has a corner of them: lots finished eighteen months ago whose
owner has stopped answering, cylinders left behind when a customer went out of
business. The shop cannot fill them, cannot sell them and cannot legally throw
them away without trying to give them back first.

The rule the shop can defend is a sequence rather than a date: the lot has to
have been ready for long enough, the owner has to have been written to, and a
further period has to have passed since that letter. Each step is checked
here; none of them is assumed from the one before.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from starstamp.model.lot import Lot, LotStatus

READY_MONTHS = 6
NOTICE_WAIT_DAYS = 60


class Standing(Enum):
    """Where a left behind lot has got to."""

    IN_HAND = "in_hand"
    OVERDUE = "overdue"
    WRITTEN_TO = "written_to"
    ABANDONED = "abandoned"

    @property
    def may_be_disposed_of(self) -> bool:
        return self is Standing.ABANDONED

    @property
    def needs_a_letter(self) -> bool:
        return self is Standing.OVERDUE


@dataclass(frozen=True)
class Abandonment:
    """One lot, and how far along the sequence it is."""

    lot_number: str
    owner_code: str
    ready_since: date | None
    written_on: date | None
    today: date

    @property
    def days_ready(self) -> int:
        if self.ready_since is None:
            return 0
        return max((self.today - self.ready_since).days, 0)

    @property
    def days_since_letter(self) -> int:
        if self.written_on is None:
            return 0
        return max((self.today - self.written_on).days, 0)

    @property
    def standing(self) -> Standing:
        if self.ready_since is None or self.days_ready < READY_MONTHS * 30:
            return Standing.IN_HAND
        if self.written_on is None:
            return Standing.OVERDUE
        if self.days_since_letter < NOTICE_WAIT_DAYS:
            return Standing.WRITTEN_TO
        return Standing.ABANDONED

    def next_step_on(self) -> date | None:
        """The day something changes, where there is one."""
        if self.ready_since is not None and self.standing is Standing.IN_HAND:
            return self.ready_since + timedelta(days=READY_MONTHS * 30)
        if self.written_on is not None and self.standing is Standing.WRITTEN_TO:
            return self.written_on + timedelta(days=NOTICE_WAIT_DAYS)
        return None

    def describe(self) -> str:
        standing = self.standing
        if standing is Standing.IN_HAND:
            return f"{self.lot_number} has been ready {self.days_ready} days"
        if standing is Standing.OVERDUE:
            return (
                f"{self.lot_number} has been ready {self.days_ready} days and nobody has "
                f"written to {self.owner_code}"
            )
        if standing is Standing.WRITTEN_TO:
            return (
                f"{self.lot_number}: {self.owner_code} was written to "
                f"{self.days_since_letter} days ago"
            )
        return f"{self.lot_number} is abandoned; {self.owner_code} was written to and did not come"


def standing_for(lot: Lot, today: date, *, written_on: date | None = None) -> Abandonment:
    """Work out where one lot has got to."""
    ready_since = None
    if lot.status is LotStatus.READY:
        ready_since = lot.promised_on or lot.received_on
    return Abandonment(
        lot_number=lot.number,
        owner_code=lot.owner_code,
        ready_since=ready_since,
        written_on=written_on,
        today=today,
    )
