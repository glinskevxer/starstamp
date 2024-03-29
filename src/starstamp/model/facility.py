"""Who is allowed to do the work, and what they are allowed to do.

A requalification is only a requalification if the facility that performed it
held an identification number for that method on that day, and if the person
who performed it was signed off for it. Both of those expire, and both of them
narrow the method matrix further than the cylinder does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from starstamp.errors import ValidationError
from starstamp.model.method import Method

_RIN = re.compile(r"^[A-Z][A-Z0-9]{2,3}$")
_BADGE = re.compile(r"^[A-Z0-9]{2,8}$")


def normalise_rin(text: str) -> str:
    """A requalifier identification number as it is stamped."""
    cleaned = text.strip().upper().replace(" ", "").replace("-", "")
    if not _RIN.match(cleaned):
        raise ValidationError(f"a RIN is three or four characters starting with a letter: {text!r}")
    return cleaned


def normalise_badge(text: str) -> str:
    cleaned = text.strip().upper().replace(" ", "")
    if not _BADGE.match(cleaned):
        raise ValidationError(f"a badge is two to eight letters or digits, got {text!r}")
    return cleaned


@dataclass(frozen=True)
class Facility:
    """The shop itself, as the regulator knows it."""

    rin: str
    name: str
    approved_from: date
    approved_until: date
    methods: frozenset[Method] = field(default_factory=frozenset)
    address: str | None = None

    def __post_init__(self) -> None:
        if self.approved_until < self.approved_from:
            raise ValidationError(f"{self.rin} cannot expire before it was issued")
        if not self.methods:
            raise ValidationError(f"{self.rin} is approved for no methods at all")

    def approved_on(self, day: date) -> bool:
        return self.approved_from <= day <= self.approved_until

    def may_perform(self, method: Method, day: date) -> bool:
        return method in self.methods and self.approved_on(day)

    def lapsed_by(self, day: date) -> int:
        """Days past expiry, or zero while it is still current."""
        if day <= self.approved_until:
            return 0
        return (day - self.approved_until).days

    def __str__(self) -> str:
        return f"{self.rin} {self.name}"


@dataclass(frozen=True)
class Technician:
    """One person on the bench, and what they are signed off for."""

    badge: str
    name: str
    methods: frozenset[Method]
    qualified_from: date
    qualified_until: date | None = None

    def __post_init__(self) -> None:
        if self.qualified_until is not None and self.qualified_until < self.qualified_from:
            raise ValidationError(f"{self.badge} cannot lapse before being signed off")
        if not self.methods:
            raise ValidationError(f"{self.badge} is signed off for no methods")

    def qualified_on(self, day: date) -> bool:
        if day < self.qualified_from:
            return False
        return self.qualified_until is None or day <= self.qualified_until

    def may_perform(self, method: Method, day: date) -> bool:
        return method in self.methods and self.qualified_on(day)

    def __str__(self) -> str:
        return f"{self.badge} {self.name}"
