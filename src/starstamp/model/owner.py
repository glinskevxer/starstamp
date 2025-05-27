"""The customer whose cylinders these are.

A requalification shop almost never owns the cylinders on its floor. Every
cylinder belongs to a distributor, a fire district or a welding shop, and the
account is what the invoice and the condemnation notice both hang off.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from starstamp.errors import ValidationError

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_]{1,15}$")


def normalise_owner_code(text: str) -> str:
    cleaned = text.strip().upper().replace(" ", "_").replace("-", "_")
    if not _CODE.match(cleaned):
        raise ValidationError(f"account code must be 2 to 16 letters or digits, got {text!r}")
    return cleaned


@dataclass(frozen=True)
class OwnerAccount:
    """One customer account."""

    code: str
    name: str
    opened_on: date
    contact: str | None = None
    terms_days: int = 30
    closed_on: date | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("an account needs a name")
        if self.email is not None and "@" not in self.email:
            raise ValidationError(f"that is not an email address: {self.email!r}")
        if self.terms_days < 0 or self.terms_days > 180:
            raise ValidationError(f"terms of {self.terms_days} days are not a thing here")
        if self.closed_on is not None and self.closed_on < self.opened_on:
            raise ValidationError("an account cannot close before it opened")

    @property
    def can_be_written_to(self) -> bool:
        """Whether the shop has anywhere to send a condemnation notice."""
        return bool(self.address or self.email)

    def postal_block(self) -> str:
        """The account as it goes at the top of a letter."""
        lines = [self.name]
        if self.contact:
            lines.append(f"attn {self.contact}")
        if self.address:
            lines.extend(part.strip() for part in self.address.split(",") if part.strip())
        return "\n".join(lines)

    @property
    def is_open(self) -> bool:
        return self.closed_on is None

    def open_on(self, day: date) -> bool:
        """Whether the account was open for business on a given day."""
        if day < self.opened_on:
            return False
        return self.closed_on is None or day <= self.closed_on

    def __str__(self) -> str:
        return f"{self.code} {self.name}"
