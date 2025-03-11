"""Charging for cylinders left in the shop.

A shop with four hundred square feet of floor cannot store a customer's
cylinders indefinitely, and the ones that sit longest are almost always the
ones somebody has stopped answering the phone about. So the free period is a
shop setting, the clock runs from the day the lot came in, and the charge is a
daily rate out of the price book like anything else.

The clock stops when the lot goes back, not when the work finished. A lot the
shop finished in a week and the customer collected in July was in the way for
all of June.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.lot import Lot
from starstamp.model.money import Money

STORAGE_CODE = "STORAGE"


@dataclass(frozen=True)
class StorageDays:
    """How long a lot sat, and how much of that is chargeable."""

    lot_number: str
    owner_code: str
    received_on: date
    until: date
    free_days: int

    @property
    def days_held(self) -> int:
        return max((self.until - self.received_on).days, 0)

    @property
    def chargeable_days(self) -> int:
        return max(self.days_held - self.free_days, 0)

    @property
    def is_chargeable(self) -> bool:
        return self.chargeable_days > 0

    def charge(self, daily_rate: Money) -> Money:
        return daily_rate.times(self.chargeable_days)

    def describe(self) -> str:
        if not self.is_chargeable:
            return f"{self.lot_number} held {self.days_held} days, inside the {self.free_days} free"
        return (
            f"{self.lot_number} held {self.days_held} days, "
            f"{self.chargeable_days} of them chargeable"
        )


def days_for(lot: Lot, today: date, free_days: int) -> StorageDays:
    """How long one lot has been in the way."""
    return StorageDays(
        lot_number=lot.number,
        owner_code=lot.owner_code,
        received_on=lot.received_on,
        until=lot.returned_on or today,
        free_days=free_days,
    )


def chargeable(lots: list[Lot], today: date, free_days: int) -> list[StorageDays]:
    """Every lot with something to charge for, longest first."""
    found = [days_for(lot, today, free_days) for lot in lots]
    return sorted(
        (item for item in found if item.is_chargeable),
        key=lambda item: (-item.chargeable_days, item.lot_number),
    )
