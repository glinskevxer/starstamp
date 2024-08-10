"""What the shop charges, and when it started charging it.

A price is dated for the same reason a calibration certificate is: an invoice
raised today for work done in March has to carry March's price. Nothing here
looks up "the current price" without being told which day it means.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from starstamp.errors import NotFoundError, ValidationError
from starstamp.model.method import Method
from starstamp.model.money import Money

_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,15}$")

REQUALIFICATION_CODES: dict[Method, str] = {
    Method.VOLUMETRIC: "REQUAL_WJ",
    Method.DIRECT_EXPANSION: "REQUAL_DE",
    Method.PROOF_PRESSURE: "REQUAL_PROOF",
    Method.EXTERNAL_VISUAL: "REQUAL_VISUAL",
    Method.ULTRASONIC: "REQUAL_UT",
    Method.ACETYLENE_VISUAL: "REQUAL_ACET",
}

HANDLING = "HANDLING"
CONDEMNATION = "CONDEMN"
VALVE = "VALVE"


def normalise_charge_code(text: str) -> str:
    cleaned = text.strip().upper().replace(" ", "_").replace("-", "_")
    if not _CODE.match(cleaned):
        raise ValidationError(f"a charge code is 2 to 16 characters, got {text!r}")
    return cleaned


def code_for(method: Method) -> str:
    return REQUALIFICATION_CODES[method]


@dataclass(frozen=True)
class PriceItem:
    """One charge at one price, for a stretch of time."""

    code: str
    description: str
    amount: Money
    effective_from: date
    effective_until: date | None = None

    def __post_init__(self) -> None:
        normalise_charge_code(self.code)
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise ValidationError(f"{self.code} would end before it started")

    def applies_on(self, day: date) -> bool:
        if day < self.effective_from:
            return False
        return self.effective_until is None or day <= self.effective_until

    def __str__(self) -> str:
        return f"{self.code} {self.amount.with_symbol()} from {self.effective_from}"


@dataclass(frozen=True)
class PriceBook:
    """Every price the shop has ever charged, which is what dating them means."""

    items: tuple[PriceItem, ...] = ()

    def on(self, code: str, day: date) -> PriceItem:
        """The price in force for a code on a day."""
        wanted = normalise_charge_code(code)
        candidates = [item for item in self.items if item.code == wanted and item.applies_on(day)]
        if not candidates:
            raise NotFoundError(f"no price for {wanted} on {day.isoformat()}")
        return max(candidates, key=lambda item: item.effective_from)

    def amount(self, code: str, day: date) -> Money:
        return self.on(code, day).amount

    def codes(self) -> list[str]:
        return sorted({item.code for item in self.items})

    def with_item(self, item: PriceItem) -> PriceBook:
        return PriceBook((*self.items, item))
