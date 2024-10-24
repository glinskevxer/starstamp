"""Valve outlet connections, which are how the gas industry stops mistakes.

Every compressed gas has a connection assigned to it, and the assignments are
deliberately incompatible: an oxygen regulator will not thread onto a hydrogen
cylinder, because hydrogen is left hand threaded and oxygen is not. That is
the whole safety argument, and it only works if the valve in the cylinder is
the one the gas calls for. A shop that fits whatever valve is on the shelf has
quietly removed the interlock.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from starstamp.errors import ValidationError

_OUTLET = re.compile(r"^(?:CGA[- ]?)?(?P<number>\d{3})$")


class Thread(Enum):
    """Which way the connection is threaded."""

    RIGHT_HAND = "right_hand"
    LEFT_HAND = "left_hand"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")


@dataclass(frozen=True)
class Outlet:
    """One CGA valve outlet connection."""

    number: str
    description: str
    thread: Thread = Thread.RIGHT_HAND

    def __str__(self) -> str:
        return f"CGA {self.number}"


_OUTLETS: dict[str, Outlet] = {}


def _add(outlet: Outlet) -> Outlet:
    _OUTLETS[outlet.number] = outlet
    return outlet


CGA_540 = _add(Outlet("540", "oxygen and oxidising service"))
CGA_580 = _add(Outlet("580", "inert service, nitrogen argon helium"))
CGA_590 = _add(Outlet("590", "industrial air"))
CGA_350 = _add(Outlet("350", "hydrogen and flammable service", Thread.LEFT_HAND))
CGA_320 = _add(Outlet("320", "carbon dioxide"))
CGA_326 = _add(Outlet("326", "nitrous oxide"))
CGA_510 = _add(Outlet("510", "acetylene, pol style", Thread.LEFT_HAND))
CGA_555 = _add(Outlet("555", "liquefied petroleum gas", Thread.LEFT_HAND))
CGA_660 = _add(Outlet("660", "anhydrous ammonia"))
CGA_330 = _add(Outlet("330", "chlorine"))
CGA_346 = _add(Outlet("346", "breathing air"))
CGA_870 = _add(Outlet("870", "medical oxygen, pin index"))

_BY_SERVICE: dict[str, Outlet] = {
    "O2": CGA_540,
    "O2M": CGA_870,
    "N2": CGA_580,
    "AR": CGA_580,
    "HE": CGA_580,
    "ARCO2": CGA_580,
    "AIR": CGA_590,
    "SCBA": CGA_346,
    "H2": CGA_350,
    "CH4": CGA_350,
    "C2H4": CGA_350,
    "CO2": CGA_320,
    "N2O": CGA_326,
    "C2H2": CGA_510,
    "LPG": CGA_555,
    "NH3": CGA_660,
    "CL2": CGA_330,
    "SO2": CGA_330,
    "HCL": CGA_330,
}


def parse_outlet(text: str) -> Outlet:
    """Read an outlet off a valve or off a work order."""
    match = _OUTLET.match(text.strip().upper().replace("  ", " "))
    if match is None:
        raise ValidationError(f"a valve outlet is a CGA number, got {text!r}")
    outlet = _OUTLETS.get(match.group("number"))
    if outlet is None:
        known = ", ".join(sorted(_OUTLETS))
        raise ValidationError(f"the shop stocks CGA {known}, not {match.group('number')}")
    return outlet


def outlet_for_service(service_code: str) -> Outlet:
    """The outlet a gas calls for."""
    outlet = _BY_SERVICE.get(service_code.strip().upper())
    if outlet is None:
        raise ValidationError(f"no valve outlet is assigned to {service_code}")
    return outlet


def all_outlets() -> list[Outlet]:
    return [_OUTLETS[number] for number in sorted(_OUTLETS)]
