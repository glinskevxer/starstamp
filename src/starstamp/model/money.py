"""Money, in whole cents and nothing else.

A requalification is fourteen dollars and a lot is forty cylinders, so the
arithmetic is small. It is also the arithmetic a customer checks with a
calculator, and a total that is a cent out because it went through a float is
a phone call the shop does not need.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from starstamp.errors import ValidationError

_AMOUNT = re.compile(r"^\$?(?P<whole>\d{1,9})(?:\.(?P<cents>\d{1,2}))?$")


@dataclass(frozen=True, order=True)
class Money:
    """An amount in cents. Never negative here: a credit is its own thing."""

    cents: int

    def __post_init__(self) -> None:
        if self.cents < 0:
            raise ValidationError(f"a price cannot be negative, got {self.cents} cents")

    @classmethod
    def parse(cls, text: str) -> Money:
        match = _AMOUNT.match(text.strip())
        if match is None:
            raise ValidationError(f"an amount looks like 14.50, got {text!r}")
        cents: str = (match.group("cents") or "").ljust(2, "0")
        return cls(int(match.group("whole")) * 100 + int(cents))

    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    def plus(self, other: Money) -> Money:
        return Money(self.cents + other.cents)

    def times(self, count: int) -> Money:
        if count < 0:
            raise ValidationError("a line cannot have a negative count")
        return Money(self.cents * count)

    def share_of(self, numerator: int, denominator: int) -> Money:
        """A share, rounded half up, so a split of a total still adds back."""
        if denominator <= 0:
            raise ValidationError("cannot take a share of nothing")
        return Money((self.cents * numerator * 2 + denominator) // (denominator * 2))

    def __str__(self) -> str:
        return f"{self.cents // 100}.{self.cents % 100:02d}"

    def with_symbol(self) -> str:
        return f"${self}"


def total(amounts: list[Money]) -> Money:
    running = Money.zero()
    for amount in amounts:
        running = running.plus(amount)
    return running
