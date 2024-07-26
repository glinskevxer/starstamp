"""Cylinders arrive in lots and leave in lots.

A distributor drops forty cylinders on a Tuesday and wants them back by the
end of the month. Nothing in the requalification rules cares about that, and
everything about running the shop does: the promise date is what the front
counter answers the phone with, and the lot is what a condemned cylinder has
to be explained against.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

from starstamp.errors import ValidationError

_NUMBER = re.compile(r"^L(?P<year>\d{4})-(?P<serial>\d{4})$")


class LotStatus(Enum):
    """Where a lot is in its pass through the shop."""

    RECEIVED = "received"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    RETURNED = "returned"

    @property
    def is_open(self) -> bool:
        return self is not LotStatus.RETURNED

    @property
    def accepts_work(self) -> bool:
        return self in {LotStatus.RECEIVED, LotStatus.IN_PROGRESS}


def format_lot_number(year: int, serial: int) -> str:
    if not 1900 <= year <= 2199:
        raise ValidationError(f"a lot year outside anything real: {year}")
    if not 1 <= serial <= 9999:
        raise ValidationError(f"a lot serial runs 1 to 9999, got {serial}")
    return f"L{year:04d}-{serial:04d}"


def parse_lot_number(text: str) -> tuple[int, int]:
    match = _NUMBER.match(text.strip().upper())
    if match is None:
        raise ValidationError(f"a lot number is LYYYY-NNNN, got {text!r}")
    return int(match.group("year")), int(match.group("serial"))


@dataclass(frozen=True)
class Lot:
    """One delivery of cylinders from one account."""

    number: str
    owner_code: str
    received_on: date
    promised_on: date | None = None
    status: LotStatus = LotStatus.RECEIVED
    carrier: str | None = None
    note: str | None = None
    returned_on: date | None = None

    def __post_init__(self) -> None:
        parse_lot_number(self.number)
        if self.promised_on is not None and self.promised_on < self.received_on:
            raise ValidationError(f"{self.number} was promised before it arrived")
        if self.returned_on is not None and self.returned_on < self.received_on:
            raise ValidationError(f"{self.number} cannot go back before it arrived")
        if (self.returned_on is None) != (self.status is not LotStatus.RETURNED):
            raise ValidationError(
                f"{self.number} is {self.status.value} and its return date does not agree"
            )

    def days_in_shop(self, today: date) -> int:
        end = self.returned_on or today
        return (end - self.received_on).days

    def is_late(self, today: date) -> bool:
        """Late means past the promise and still here."""
        if self.promised_on is None or self.returned_on is not None:
            return False
        return today > self.promised_on

    def days_late(self, today: date) -> int:
        if not self.is_late(today) or self.promised_on is None:
            return 0
        return (today - self.promised_on).days

    def __str__(self) -> str:
        return f"{self.number} for {self.owner_code}"


@dataclass(frozen=True)
class LotLine:
    """One cylinder on a lot, and what became of it."""

    lot_number: str
    cylinder_key: str
    added_on: date
    disposition: str | None = None
    event_id: int | None = None

    @property
    def is_settled(self) -> bool:
        return self.disposition is not None

    def __str__(self) -> str:
        return f"{self.cylinder_key} on {self.lot_number}: {self.disposition or 'open'}"
