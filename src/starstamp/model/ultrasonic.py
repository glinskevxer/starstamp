"""Ultrasonic examination: measuring the wall instead of stretching it.

An ultrasonic requalification does not pressurise the cylinder at all. It
measures the wall at a set of points and compares each reading against the
minimum wall the cylinder was designed to. That makes it a different shape of
evidence from a water jacket test, and the difference matters: a volumetric
test asks whether the cylinder as a whole came back, and this asks whether any
one spot has thinned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from starstamp.errors import ValidationError

_POSITION = re.compile(r"^(?P<band>[A-Z])(?P<index>\d{1,2})$")
MINIMUM_POINTS = 6


class Band(Enum):
    """Where up the cylinder a reading was taken."""

    SHOULDER = "S"
    UPPER = "U"
    MIDDLE = "M"
    LOWER = "L"
    BASE = "B"

    @property
    def label(self) -> str:
        return {
            "S": "shoulder",
            "U": "upper barrel",
            "M": "mid barrel",
            "L": "lower barrel",
            "B": "base",
        }[self.value]


@dataclass(frozen=True, order=True)
class Position:
    """One spot on the cylinder, as the scan sheet names it."""

    band: Band
    index: int

    def __post_init__(self) -> None:
        if not 1 <= self.index <= 24:
            raise ValidationError(f"a scan position runs 1 to 24, got {self.index}")

    @classmethod
    def parse(cls, text: str) -> Position:
        match = _POSITION.match(text.strip().upper())
        if match is None:
            raise ValidationError(f"a scan position is a band and a number, got {text!r}")
        try:
            band = Band(match.group("band"))
        except ValueError as exc:
            bands = ", ".join(item.value for item in Band)
            raise ValidationError(f"the bands are {bands}, not {match.group('band')}") from exc
        return cls(band, int(match.group("index")))

    def __str__(self) -> str:
        return f"{self.band.value}{self.index}"


@dataclass(frozen=True)
class Reading:
    """One wall thickness reading in thousandths of an inch."""

    position: Position
    thousandths_in: int

    def __post_init__(self) -> None:
        if self.thousandths_in <= 0:
            raise ValidationError(f"{self.position} was recorded as {self.thousandths_in}")

    def __str__(self) -> str:
        return f"{self.position} {self.thousandths_in / 1000:.3f} in"


@dataclass(frozen=True)
class Scan:
    """A whole examination: every point, taken on one day."""

    readings: tuple[Reading, ...]

    def __post_init__(self) -> None:
        seen = {reading.position for reading in self.readings}
        if len(seen) != len(self.readings):
            raise ValidationError("the same position was recorded twice on one scan")

    @property
    def count(self) -> int:
        return len(self.readings)

    @property
    def thinnest(self) -> Reading:
        if not self.readings:
            raise ValidationError("an empty scan has no thinnest point")
        return min(self.readings, key=lambda reading: reading.thousandths_in)

    @property
    def bands(self) -> frozenset[Band]:
        return frozenset(reading.position.band for reading in self.readings)

    def below(self, floor_thousandths: int) -> tuple[Reading, ...]:
        return tuple(
            reading for reading in self.readings if reading.thousandths_in < floor_thousandths
        )

    def describe(self) -> str:
        if not self.readings:
            return "no readings"
        return f"{self.count} points across {len(self.bands)} bands, thinnest {self.thinnest}"
