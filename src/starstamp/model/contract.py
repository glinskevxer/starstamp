"""What a particular account pays, when it is not what everybody pays.

A distributor sending four hundred cylinders a year negotiates, and what they
negotiate is one of two things: a flat price for a charge code, or a discount
off the book. Both are dated the same way the price book is, because an
invoice raised late still has to bill the agreement that was in force when the
work was done.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.errors import NotFoundError, ValidationError
from starstamp.model.money import Money
from starstamp.model.pricing import normalise_charge_code


@dataclass(frozen=True)
class ContractTerm:
    """One account's price for one charge code, over a stretch of time."""

    owner_code: str
    code: str
    effective_from: date
    amount: Money | None = None
    discount_percent: Fraction | None = None
    effective_until: date | None = None

    def __post_init__(self) -> None:
        normalise_charge_code(self.code)
        if (self.amount is None) == (self.discount_percent is None):
            raise ValidationError(
                "a term is either a flat price or a discount, and it has to be one of them"
            )
        if self.discount_percent is not None and not 0 < self.discount_percent < 100:
            raise ValidationError(
                f"a discount runs between 0 and 100 percent, got {self.discount_percent}"
            )
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise ValidationError(f"{self.code} for {self.owner_code} ends before it starts")

    @property
    def is_flat(self) -> bool:
        return self.amount is not None

    def applies_on(self, day: date) -> bool:
        if day < self.effective_from:
            return False
        return self.effective_until is None or day <= self.effective_until

    def price_from(self, book_price: Money) -> Money:
        """What the account pays, given what everybody else pays."""
        if self.amount is not None:
            return self.amount
        assert self.discount_percent is not None
        kept = Fraction(100) - self.discount_percent
        exact = Fraction(book_price.cents) * kept / 100
        return Money((exact.numerator * 2 + exact.denominator) // (exact.denominator * 2))

    def __str__(self) -> str:
        if self.amount is not None:
            return f"{self.owner_code} {self.code} at {self.amount.with_symbol()}"
        return f"{self.owner_code} {self.code} less {float(self.discount_percent or 0):.1f}%"


@dataclass(frozen=True)
class Contract:
    """Every term an account has ever had."""

    owner_code: str
    terms: tuple[ContractTerm, ...] = ()

    def term_on(self, code: str, day: date) -> ContractTerm | None:
        wanted = normalise_charge_code(code)
        candidates = [term for term in self.terms if term.code == wanted and term.applies_on(day)]
        if not candidates:
            return None
        return max(candidates, key=lambda term: term.effective_from)

    def price(self, code: str, day: date, book_price: Money) -> Money:
        term = self.term_on(code, day)
        if term is None:
            return book_price
        return term.price_from(book_price)

    def require_term(self, code: str, day: date) -> ContractTerm:
        term = self.term_on(code, day)
        if term is None:
            raise NotFoundError(
                f"{self.owner_code} has no agreed price for {code} on {day.isoformat()}"
            )
        return term

    def codes(self) -> list[str]:
        return sorted({term.code for term in self.terms})
