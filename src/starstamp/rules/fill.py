"""Whether a cylinder may be filled today, and how far.

This is the question the filling plant asks and the one the whole book exists
to answer. It consumes everything the bench decided: the interval came from
the method, the star came from the readings, the plus came from a tighter
reading of the same numbers, and the gas the cylinder is dedicated to came off
its marks. None of that is recomputed here.

Two refusals are worth keeping apart. A cylinder that is out of test may be
filled again as soon as it is requalified. A cylinder that is condemned never
may. The plant treats those differently and so does this.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.model.cylinder import Cylinder, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.service import GasService
from starstamp.model.units import Pressure
from starstamp.rules.interval import due_month, is_out_of_test, life_expired

CITATION = "49 CFR 173.301"

PLUS_OVERFILL = Fraction(11, 10)
LIQUEFIED_FILLING_DENSITY = Fraction(50)


@dataclass(frozen=True)
class FillDecision:
    """Whether the plant may put gas in it, and the ceiling if so."""

    cylinder_key: str
    gas: GasService
    day: date
    refusals: tuple[str, ...]
    due: StampedMonth | None
    max_pressure: Pressure | None
    filling_density_percent: Fraction | None
    terminal: bool = False

    @property
    def allowed(self) -> bool:
        return not self.refusals

    def describe(self) -> str:
        if self.allowed:
            if self.max_pressure is not None:
                return f"{self.cylinder_key} may be filled with {self.gas} to {self.max_pressure}"
            density = self.filling_density_percent
            return (
                f"{self.cylinder_key} may be filled with {self.gas} to "
                f"{float(density or 0):.0f}% filling density"
            )
        head = "never" if self.terminal else "not today"
        return f"{self.cylinder_key} {head}: " + "; ".join(self.refusals)


def ceiling_for(cylinder: Cylinder, gas: GasService, *, plus: bool) -> Pressure | None:
    """The most pressure the plant may put in, or nothing for a liquefied gas."""
    if gas.liquefied or gas.dissolved:
        return None
    service_pressure = cylinder.specification.service_pressure
    if service_pressure is None:
        return None
    if plus and not gas.liquefied:
        return service_pressure.scaled(PLUS_OVERFILL)
    return service_pressure


def decide(
    cylinder: Cylinder,
    gas: GasService,
    day: date,
    last_pass: RequalificationEvent | None,
    *,
    starred: bool = False,
    plus: bool = False,
) -> FillDecision:
    """Answer the plant's question, listing everything in the way."""
    refusals: list[str] = []
    terminal = False
    due: StampedMonth | None = None

    if cylinder.status is CylinderStatus.CONDEMNED:
        refusals.append("the cylinder is condemned")
        terminal = True
    elif cylinder.status is CylinderStatus.SCRAPPED:
        refusals.append("the cylinder has been scrapped")
        terminal = True
    elif cylinder.status is CylinderStatus.LOST:
        refusals.append("the cylinder is not on the floor")
        terminal = True
    elif cylinder.status is CylinderStatus.AWAITING_REPAIR:
        refusals.append("the cylinder is waiting on a repair")

    if life_expired(cylinder, day):
        refusals.append("the cylinder is past the service life of its specification")
        terminal = True

    if last_pass is None or last_pass.outcome is not Outcome.PASS:
        refusals.append("no standing requalification")
    else:
        due = due_month(cylinder, last_pass.marked_month, last_pass.method, starred=starred)
        if is_out_of_test(due, day):
            refusals.append(f"out of test since {due.long_form()}")

    if gas is not cylinder.service:
        if cylinder.service.requires_dedicated_cylinder:
            refusals.append(f"the cylinder is dedicated to {cylinder.service}")
        elif gas.requires_dedicated_cylinder:
            refusals.append(f"{gas} needs a cylinder dedicated to it")

    ceiling = ceiling_for(
        cylinder, gas, plus=plus and not is_out_of_test(due or StampedMonth.of(day), day)
    )
    density = LIQUEFIED_FILLING_DENSITY if (gas.liquefied or gas.dissolved) else None
    return FillDecision(
        cylinder_key=str(cylinder.key),
        gas=gas,
        day=day,
        refusals=tuple(refusals),
        due=due,
        max_pressure=ceiling,
        filling_density_percent=density,
        terminal=terminal,
    )
