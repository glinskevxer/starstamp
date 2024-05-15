"""The cylinder as the shop knows it: what is stamped on it, plus where it is.

Everything on a cylinder that matters is stamped into the metal, and the
stamping is the only record that travels with it. The book holds a
transcription of those marks and nothing else about the cylinder's
construction, because anything the book invented would be a guess about a
piece of steel somebody else made in 1974.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum

from starstamp.errors import ValidationError
from starstamp.model.dates import StampedMonth
from starstamp.model.service import GasService
from starstamp.model.specification import SpecFamily, Specification
from starstamp.model.units import Expansion, Pressure

_SERIAL = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,19}$")
_SYMBOL = re.compile(r"^[A-Z][A-Z0-9\-\.]{0,9}$")


class CylinderStatus(Enum):
    """Where a cylinder stands, from the shop's point of view."""

    IN_SERVICE = "in_service"
    IN_SHOP = "in_shop"
    AWAITING_REPAIR = "awaiting_repair"
    CONDEMNED = "condemned"
    SCRAPPED = "scrapped"
    LOST = "lost"

    @property
    def is_terminal(self) -> bool:
        return self in {CylinderStatus.CONDEMNED, CylinderStatus.SCRAPPED, CylinderStatus.LOST}

    @property
    def accepts_work(self) -> bool:
        return self in {
            CylinderStatus.IN_SERVICE,
            CylinderStatus.IN_SHOP,
            CylinderStatus.AWAITING_REPAIR,
        }


def normalise_serial(text: str) -> str:
    cleaned = text.strip().upper().replace(" ", "")
    if not _SERIAL.match(cleaned):
        raise ValidationError(f"serial must be letters, digits and dashes, got {text!r}")
    return cleaned


def normalise_symbol(text: str) -> str:
    """The manufacturer's registered symbol, as stamped beside the serial."""
    cleaned = text.strip().upper().replace(" ", "")
    if not _SYMBOL.match(cleaned):
        raise ValidationError(f"manufacturer symbol is not a stamped symbol: {text!r}")
    return cleaned


@dataclass(frozen=True, order=True)
class CylinderKey:
    """A cylinder is identified by its maker's symbol and serial, together.

    Serials repeat across manufacturers all the time, and a shop that keys on
    the serial alone will eventually stamp one customer's cylinder with another
    customer's test.
    """

    manufacturer_symbol: str
    serial: str

    @classmethod
    def of(cls, manufacturer_symbol: str, serial: str) -> CylinderKey:
        return cls(normalise_symbol(manufacturer_symbol), normalise_serial(serial))

    @classmethod
    def parse(cls, text: str) -> CylinderKey:
        """Read the shop's shorthand, which writes the symbol first: NCI/A4471."""
        if "/" not in text:
            raise ValidationError(f"a cylinder key is SYMBOL/SERIAL, got {text!r}")
        symbol, _, serial = text.partition("/")
        return cls.of(symbol, serial)

    def __str__(self) -> str:
        return f"{self.manufacturer_symbol}/{self.serial}"


@dataclass(frozen=True)
class Cylinder:
    """A cylinder on the shop's books."""

    key: CylinderKey
    specification: Specification
    manufactured: StampedMonth
    service: GasService
    owner_code: str
    status: CylinderStatus = CylinderStatus.IN_SERVICE
    rejection_elastic_expansion: Expansion | None = None
    water_capacity_tenths_l: int | None = None
    tare_hundredths_lb: int | None = None
    nominal_wall_thousandths_in: int | None = None
    wall_source: str | None = None

    def __post_init__(self) -> None:
        if self.nominal_wall_thousandths_in is not None and self.nominal_wall_thousandths_in <= 0:
            raise ValidationError("a wall thickness of zero is not a reading")
        if self.nominal_wall_thousandths_in is not None and self.wall_source is None:
            raise ValidationError("a wall thickness has to say where it came from")
        if self.water_capacity_tenths_l is not None and self.water_capacity_tenths_l <= 0:
            raise ValidationError("water capacity must be positive when it is recorded")
        if self.tare_hundredths_lb is not None and self.tare_hundredths_lb <= 0:
            raise ValidationError("tare weight must be positive when it is recorded")
        if self.service.dissolved and self.specification.family is not SpecFamily.ACETYLENE:
            raise ValidationError(
                f"{self.service} belongs in an acetylene cylinder, not {self.specification}"
            )

    @property
    def service_pressure(self) -> Pressure | None:
        return self.specification.service_pressure

    @property
    def carries_ree(self) -> bool:
        """Only seamless cylinders are marked with a rejection elastic expansion."""
        return self.specification.is_seamless

    def require_ree(self) -> Expansion:
        if self.rejection_elastic_expansion is None:
            raise ValidationError(f"{self.key} carries no marked rejection elastic expansion")
        return self.rejection_elastic_expansion

    def require_wall(self) -> int:
        """The wall thickness the visual limits are fractions of.

        There is no default here on purpose. A shop that assumes a wall will
        eventually assume one that is thicker than the cylinder in front of it.
        """
        if self.nominal_wall_thousandths_in is None:
            raise ValidationError(
                f"{self.key} has no recorded wall thickness, so nothing can be judged against it"
            )
        return self.nominal_wall_thousandths_in

    @property
    def wall_is_known(self) -> bool:
        return self.nominal_wall_thousandths_in is not None

    def with_wall(self, thousandths_in: int, source: str) -> Cylinder:
        return replace(self, nominal_wall_thousandths_in=thousandths_in, wall_source=source)

    def with_status(self, status: CylinderStatus) -> Cylinder:
        if self.status.is_terminal and status is not self.status:
            raise ValidationError(f"{self.key} is {self.status.value} and does not come back")
        return replace(self, status=status)

    def __str__(self) -> str:
        return f"{self.key} {self.specification} {self.service}"
