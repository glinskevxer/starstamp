"""Measured quantities, all of them integers underneath.

A requalification decision compares an expansion against a limit that is
itself derived from another expansion. Doing that in binary floating point
puts a cylinder on the wrong side of a limit roughly once in every few
thousand tests, and the shop cannot defend the ones it gets wrong. So every
quantity here stores an integer in its smallest stamped unit and every ratio
is an exact Fraction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from starstamp.errors import ValidationError

_DECIMAL = re.compile(r"^(?P<sign>-)?(?P<whole>\d+)(?:\.(?P<frac>\d+))?$")


def _scaled_int(text: str, places: int, what: str) -> int:
    """Parse a decimal string into an integer scaled by 10 ** places."""
    match = _DECIMAL.match(text.strip())
    if match is None:
        raise ValidationError(f"{what} must be a decimal number, got {text!r}")
    frac: str = match.group("frac") or ""
    if len(frac) > places:
        raise ValidationError(f"{what} carries more than {places} decimal places: {text!r}")
    frac = frac.ljust(places, "0")
    whole: str = match.group("whole")
    scale: int = 10**places
    value = int(whole) * scale + int(frac or "0")
    return -value if match.group("sign") else value


@dataclass(frozen=True, order=True)
class Pressure:
    """A gauge pressure in whole psi. Cylinders are stamped in whole psi."""

    psig: int

    def __post_init__(self) -> None:
        if self.psig < 0:
            raise ValidationError(f"pressure cannot be negative, got {self.psig}")

    @classmethod
    def parse(cls, text: str) -> Pressure:
        cleaned = text.strip().lower().removesuffix("psig").removesuffix("psi").strip()
        if not cleaned.isdigit():
            raise ValidationError(f"pressure must be whole psi, got {text!r}")
        return cls(int(cleaned))

    def scaled(self, factor: Fraction) -> Pressure:
        """Scale by an exact factor, rounding half up to whole psi."""
        exact = Fraction(self.psig) * factor
        return Pressure((exact.numerator * 2 + exact.denominator) // (exact.denominator * 2))

    def __str__(self) -> str:
        return f"{self.psig} psig"


@dataclass(frozen=True, order=True)
class Expansion:
    """A volumetric expansion in tenths of a cubic centimetre.

    Test equipment reads to 0.1 cc and the record of test is written the same
    way, so tenths is the natural integer here.
    """

    tenths_cc: int

    def __post_init__(self) -> None:
        if self.tenths_cc < 0:
            raise ValidationError(f"expansion cannot be negative, got {self.tenths_cc}")

    @classmethod
    def parse(cls, text: str) -> Expansion:
        return cls(_scaled_int(text, 1, "expansion"))

    def ratio_to(self, other: Expansion) -> Fraction:
        """This expansion as an exact fraction of another."""
        if other.tenths_cc == 0:
            raise ValidationError("cannot take a ratio against a zero expansion")
        return Fraction(self.tenths_cc, other.tenths_cc)

    def __str__(self) -> str:
        return f"{self.tenths_cc // 10}.{self.tenths_cc % 10} cc"
