"""The specification stamped into the crown of a cylinder.

The spec is the first thing read off a cylinder and the last word on most of
what follows. It fixes the service pressure, it decides which requalification
methods are legal, and it decides whether the cylinder can ever wear a star.
Everything downstream asks this module rather than matching on strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from starstamp.errors import ValidationError
from starstamp.model.units import Pressure


class SpecFamily(Enum):
    """The construction the spec describes, which is what the rules key on."""

    SEAMLESS_STEEL = "seamless_steel"
    SEAMLESS_ALUMINUM = "seamless_aluminum"
    WELDED_STEEL = "welded_steel"
    HIGH_STRENGTH_STEEL = "high_strength_steel"
    ACETYLENE = "acetylene"
    SPECIAL_PERMIT = "special_permit"
    UN_ISO = "un_iso"


_FAMILY_BY_CODE = {
    "3A": SpecFamily.SEAMLESS_STEEL,
    "3AA": SpecFamily.SEAMLESS_STEEL,
    "3AAX": SpecFamily.SEAMLESS_STEEL,
    "3AL": SpecFamily.SEAMLESS_ALUMINUM,
    "3T": SpecFamily.SEAMLESS_STEEL,
    "3HT": SpecFamily.HIGH_STRENGTH_STEEL,
    "4B": SpecFamily.WELDED_STEEL,
    "4BA": SpecFamily.WELDED_STEEL,
    "4BW": SpecFamily.WELDED_STEEL,
    "4E": SpecFamily.WELDED_STEEL,
    "8": SpecFamily.ACETYLENE,
    "8AL": SpecFamily.ACETYLENE,
}

_PLAIN = re.compile(r"^(?P<code>[0-9]+[A-Z]*)(?P<pressure>\d{2,5})?$")
_PERMIT = re.compile(r"^(?:SP|E)[- ]?(?P<number>\d{3,6})$")
_UN = re.compile(r"^ISO(?P<part>\d{4}(?:-\d)?)$")


@dataclass(frozen=True)
class Specification:
    """A parsed specification marking."""

    family: SpecFamily
    code: str
    service_pressure: Pressure | None
    permit_number: str | None = None

    @property
    def is_seamless(self) -> bool:
        return self.family in {SpecFamily.SEAMLESS_STEEL, SpecFamily.SEAMLESS_ALUMINUM}

    @property
    def is_steel(self) -> bool:
        return self.family in {
            SpecFamily.SEAMLESS_STEEL,
            SpecFamily.WELDED_STEEL,
            SpecFamily.HIGH_STRENGTH_STEEL,
        }

    @property
    def carries_service_pressure(self) -> bool:
        """Acetylene cylinders are not marked with a service pressure."""
        return self.family is not SpecFamily.ACETYLENE

    def require_service_pressure(self) -> Pressure:
        if self.service_pressure is None:
            raise ValidationError(f"{self} carries no service pressure")
        return self.service_pressure

    def __str__(self) -> str:
        if self.permit_number is not None:
            return f"DOT-SP {self.permit_number}"
        if self.family is SpecFamily.UN_ISO:
            return f"UN ISO {self.code}"
        if self.service_pressure is None:
            return f"DOT-{self.code}"
        return f"DOT-{self.code}{self.service_pressure.psig}"


def parse_specification(text: str) -> Specification:
    """Read a spec marking in any of the shapes that show up on the bench."""
    cleaned = text.strip().upper().replace("DOT", "").replace("UN", "")
    cleaned = cleaned.lstrip("-/ ").replace(" ", "")
    if not cleaned:
        raise ValidationError(f"empty specification: {text!r}")

    permit = _PERMIT.match(cleaned)
    if permit is not None:
        return Specification(
            family=SpecFamily.SPECIAL_PERMIT,
            code="SP",
            service_pressure=None,
            permit_number=permit.group("number"),
        )

    un = _UN.match(cleaned)
    if un is not None:
        return Specification(SpecFamily.UN_ISO, un.group("part"), None)

    plain = _PLAIN.match(cleaned)
    if plain is None:
        raise ValidationError(f"unreadable specification: {text!r}")
    code: str = plain.group("code")
    family = _FAMILY_BY_CODE.get(code)
    if family is None:
        raise ValidationError(f"unknown specification family: {code!r}")
    raw_pressure: str | None = plain.group("pressure")
    if raw_pressure is None:
        if family is not SpecFamily.ACETYLENE:
            raise ValidationError(f"{code} must carry a service pressure")
        return Specification(family, code, None)
    if family is SpecFamily.ACETYLENE:
        raise ValidationError(f"{code} is not marked with a service pressure")
    return Specification(family, code, Pressure(int(raw_pressure)))
