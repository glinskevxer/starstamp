"""An invoice, as the shop raises it.

Every line names the work it came from: the day, the cylinder and the record
of test. A customer who queries a line gets the record of test back, which is
the only answer worth giving.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from starstamp.errors import ValidationError
from starstamp.model.money import Money, total

_NUMBER = re.compile(r"^I(?P<year>\d{4})-(?P<serial>\d{4})$")


def format_invoice_number(year: int, serial: int) -> str:
    if not 1 <= serial <= 9999:
        raise ValidationError(f"an invoice serial runs 1 to 9999, got {serial}")
    return f"I{year:04d}-{serial:04d}"


def parse_invoice_number(text: str) -> tuple[int, int]:
    match = _NUMBER.match(text.strip().upper())
    if match is None:
        raise ValidationError(f"an invoice number is IYYYY-NNNN, got {text!r}")
    return int(match.group("year")), int(match.group("serial"))


@dataclass(frozen=True)
class InvoiceLine:
    """One charge, and the work it came from."""

    code: str
    description: str
    performed_on: date
    unit: Money
    count: int = 1
    cylinder_key: str | None = None
    event_id: int | None = None

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValidationError("an invoice line covers at least one thing")

    @property
    def amount(self) -> Money:
        return self.unit.times(self.count)

    def row(self) -> list[str]:
        return [
            self.performed_on.isoformat(),
            self.code,
            self.cylinder_key or "-",
            str(self.count),
            str(self.unit),
            str(self.amount),
        ]


@dataclass(frozen=True)
class Invoice:
    """A month's work for one account."""

    number: str
    owner_code: str
    raised_on: date
    due_on: date
    first_day: date
    last_day: date
    lines: tuple[InvoiceLine, ...] = ()
    settled_on: date | None = None

    def __post_init__(self) -> None:
        parse_invoice_number(self.number)
        if self.last_day < self.first_day:
            raise ValidationError(f"{self.number} covers a window that ends before it starts")
        if self.due_on < self.raised_on:
            raise ValidationError(f"{self.number} would fall due before it was raised")
        if self.settled_on is not None and self.settled_on < self.raised_on:
            raise ValidationError(f"{self.number} cannot be settled before it was raised")

    @property
    def total(self) -> Money:
        return total([line.amount for line in self.lines])

    @property
    def is_settled(self) -> bool:
        return self.settled_on is not None

    def is_overdue(self, today: date) -> bool:
        return not self.is_settled and today > self.due_on

    def days_overdue(self, today: date) -> int:
        if not self.is_overdue(today):
            return 0
        return (today - self.due_on).days

    def by_code(self) -> dict[str, Money]:
        grouped: dict[str, Money] = {}
        for line in self.lines:
            grouped[line.code] = grouped.get(line.code, Money.zero()).plus(line.amount)
        return dict(sorted(grouped.items()))

    def __str__(self) -> str:
        return f"{self.number} {self.owner_code} {self.total.with_symbol()}"


def due_date(raised_on: date, terms_days: int) -> date:
    return raised_on + timedelta(days=terms_days)
