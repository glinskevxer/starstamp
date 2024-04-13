"""The test system, and the paperwork that says its readings mean anything.

A water jacket rig is three instruments that all have to be in date at once:
the calibrated cylinder that the jacket is proved against, the pressure
indicator that says the cylinder reached test pressure, and the expansion
scale or burette that the reading is taken off. Each carries a certificate
with an expiry, and the shop runs the calibrated cylinder through the rig at
the start of every day it tests.

The daily check is the one that catches a rig going out between certificates,
which is the failure that actually happens. A certificate expiring is caught
by a calendar; a jacket with air trapped in it is caught by a known cylinder
reading three percent low.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.errors import ValidationError
from starstamp.model.units import Expansion

_SYSTEM = re.compile(r"^[A-Z][A-Z0-9\-]{1,11}$")


def normalise_system_code(text: str) -> str:
    cleaned = text.strip().upper().replace(" ", "-")
    if not _SYSTEM.match(cleaned):
        raise ValidationError(f"a test system code is 2 to 12 characters, got {text!r}")
    return cleaned


class InstrumentKind:
    """The instruments a test system is made of.

    Written as constants rather than an enum because the set is fixed by the
    rig and the names are what appear on the certificates the shop files.
    """

    CALIBRATED_CYLINDER = "calibrated_cylinder"
    PRESSURE_INDICATOR = "pressure_indicator"
    EXPANSION_SCALE = "expansion_scale"
    THICKNESS_GAUGE = "thickness_gauge"

    ALL = (CALIBRATED_CYLINDER, PRESSURE_INDICATOR, EXPANSION_SCALE, THICKNESS_GAUGE)

    @classmethod
    def parse(cls, text: str) -> str:
        cleaned = text.strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "cylinder": cls.CALIBRATED_CYLINDER,
            "gauge": cls.PRESSURE_INDICATOR,
            "transducer": cls.PRESSURE_INDICATOR,
            "scale": cls.EXPANSION_SCALE,
            "burette": cls.EXPANSION_SCALE,
            "ut": cls.THICKNESS_GAUGE,
            "ultrasonic": cls.THICKNESS_GAUGE,
        }
        if cleaned in aliases:
            return aliases[cleaned]
        if cleaned in cls.ALL:
            return cleaned
        known = ", ".join(cls.ALL)
        raise ValidationError(f"unknown instrument {text!r}; a system has {known}")


@dataclass(frozen=True)
class Certificate:
    """One instrument's calibration, as the certificate reads."""

    system_code: str
    instrument: str
    serial: str
    issued_on: date
    valid_until: date
    issued_by: str
    standard: str = "NIST traceable"

    def __post_init__(self) -> None:
        if self.valid_until < self.issued_on:
            raise ValidationError(f"{self.instrument} certificate expires before it was issued")
        if not self.serial.strip():
            raise ValidationError("a certificate has to name the instrument it covers")

    def valid_on(self, day: date) -> bool:
        return self.issued_on <= day <= self.valid_until

    def days_left(self, day: date) -> int:
        return (self.valid_until - day).days

    def __str__(self) -> str:
        return f"{self.system_code} {self.instrument} {self.serial} to {self.valid_until}"


@dataclass(frozen=True)
class SystemCheck:
    """The start of day run of a known cylinder through the rig."""

    system_code: str
    day: date
    expected: Expansion
    observed: Expansion
    tolerance_percent: Fraction = Fraction(1, 1)
    technician_badge: str | None = None

    def __post_init__(self) -> None:
        if self.expected.tenths_cc <= 0:
            raise ValidationError("the calibrated cylinder's expected expansion cannot be zero")
        if self.tolerance_percent <= 0:
            raise ValidationError("a tolerance of zero passes nothing")

    @property
    def deviation(self) -> Fraction:
        """Signed deviation as a percentage of the expected expansion."""
        difference = Fraction(self.observed.tenths_cc - self.expected.tenths_cc)
        return difference * 100 / Fraction(self.expected.tenths_cc)

    @property
    def within_tolerance(self) -> bool:
        return abs(self.deviation) <= self.tolerance_percent

    def describe(self) -> str:
        sign = "+" if self.deviation >= 0 else ""
        return (
            f"{self.system_code} on {self.day.isoformat()}: expected {self.expected}, "
            f"read {self.observed}, {sign}{float(self.deviation):.2f}%"
        )
