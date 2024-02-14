"""What the cylinder is filled with, and what that costs it.

Service is not a label. It decides whether the inside of the cylinder is
allowed to be wet, whether a ten year interval is on the table at all, and
whether the shop is even permitted to open the valve indoors. The catalogue is
small on purpose: a shop that takes in a gas it has no entry for should have to
add it deliberately.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from starstamp.errors import ValidationError


class Hazard(Enum):
    """The dominant hazard, which is what the shop's handling rules key on."""

    INERT = "inert"
    OXIDIZER = "oxidizer"
    FLAMMABLE = "flammable"
    CORROSIVE = "corrosive"
    TOXIC = "toxic"


@dataclass(frozen=True)
class GasService:
    """One gas as the shop handles it."""

    code: str
    name: str
    hazard: Hazard
    liquefied: bool = False
    dissolved: bool = False
    corrosive_when_wet: bool = False
    interval_eligible: bool = True
    requires_dedicated_cylinder: bool = False

    @property
    def is_dry_service(self) -> bool:
        """A gas that leaves no moisture behind, which the star rule needs."""
        return not self.corrosive_when_wet and self.hazard is not Hazard.CORROSIVE

    @property
    def needs_interior_inspection(self) -> bool:
        """Anything that can rust the inside gets looked at internally."""
        return self.corrosive_when_wet or self.liquefied or self.hazard is Hazard.CORROSIVE

    def __str__(self) -> str:
        return self.name


_CATALOGUE: dict[str, GasService] = {}


def _add(service: GasService) -> GasService:
    _CATALOGUE[service.code] = service
    return service


OXYGEN = _add(GasService("O2", "oxygen", Hazard.OXIDIZER))
NITROGEN = _add(GasService("N2", "nitrogen", Hazard.INERT))
ARGON = _add(GasService("AR", "argon", Hazard.INERT))
HELIUM = _add(GasService("HE", "helium", Hazard.INERT))
COMPRESSED_AIR = _add(GasService("AIR", "compressed air", Hazard.INERT))
HYDROGEN = _add(GasService("H2", "hydrogen", Hazard.FLAMMABLE))
CARBON_DIOXIDE = _add(GasService("CO2", "carbon dioxide", Hazard.INERT, liquefied=True))
NITROUS_OXIDE = _add(GasService("N2O", "nitrous oxide", Hazard.OXIDIZER, liquefied=True))
ARGON_CO2 = _add(GasService("ARCO2", "argon carbon dioxide mix", Hazard.INERT))
PROPANE = _add(GasService("LPG", "propane", Hazard.FLAMMABLE, liquefied=True))
ACETYLENE = _add(
    GasService(
        "C2H2",
        "acetylene",
        Hazard.FLAMMABLE,
        dissolved=True,
        interval_eligible=False,
        requires_dedicated_cylinder=True,
    )
)
AMMONIA = _add(
    GasService(
        "NH3",
        "anhydrous ammonia",
        Hazard.CORROSIVE,
        liquefied=True,
        corrosive_when_wet=True,
        requires_dedicated_cylinder=True,
    )
)
CHLORINE = _add(
    GasService(
        "CL2",
        "chlorine",
        Hazard.TOXIC,
        liquefied=True,
        corrosive_when_wet=True,
        requires_dedicated_cylinder=True,
    )
)
SULFUR_DIOXIDE = _add(
    GasService(
        "SO2",
        "sulfur dioxide",
        Hazard.TOXIC,
        liquefied=True,
        corrosive_when_wet=True,
        requires_dedicated_cylinder=True,
    )
)
HYDROGEN_CHLORIDE = _add(
    GasService(
        "HCL",
        "hydrogen chloride",
        Hazard.CORROSIVE,
        liquefied=True,
        corrosive_when_wet=True,
        requires_dedicated_cylinder=True,
    )
)
METHANE = _add(GasService("CH4", "methane", Hazard.FLAMMABLE))
ETHYLENE = _add(GasService("C2H4", "ethylene", Hazard.FLAMMABLE, liquefied=True))
BREATHING_AIR = _add(GasService("SCBA", "breathing air", Hazard.INERT))
MEDICAL_OXYGEN = _add(GasService("O2M", "medical oxygen", Hazard.OXIDIZER))


def lookup_service(code: str) -> GasService:
    """Find a gas by its shop code. Unknown gases are a refusal, not a guess."""
    key = code.strip().upper().replace("-", "").replace(" ", "")
    service = _CATALOGUE.get(key)
    if service is None:
        known = ", ".join(sorted(_CATALOGUE))
        raise ValidationError(f"unknown gas service {code!r}; the book knows {known}")
    return service


def all_services() -> list[GasService]:
    return [_CATALOGUE[code] for code in sorted(_CATALOGUE)]
