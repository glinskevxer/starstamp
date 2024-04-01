"""Whether this shop, this person and this cylinder can do this today.

Three independent narrowings meet here and none of them subsumes the others.
The cylinder decides which methods exist for it, the facility's approval
decides which of those the shop may perform, and the technician's sign off
decides which of those this person may perform. A method that survives all
three is the only kind that produces a requalification.

The order the checks run in is the order the refusals are useful in. A method
the cylinder never takes is an error in the work order; a method the shop is
not approved for is a scheduling problem; a method the person is not signed
off for is a matter of who picks the cylinder up. Reporting the last of those
when the first is also true sends the wrong person looking.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import Cylinder
from starstamp.model.facility import Facility, Technician
from starstamp.model.method import Method
from starstamp.rules.method_matrix import permitted_methods, require_permitted

CITATION = "49 CFR 180.205"


@dataclass(frozen=True)
class Authorisation:
    """A method, cleared for a cylinder by a shop and a person on a day."""

    cylinder: Cylinder
    facility: Facility
    technician: Technician
    method: Method
    day: date

    def __str__(self) -> str:
        return (
            f"{self.method.label} on {self.cylinder.key} by {self.technician.badge} "
            f"under {self.facility.rin} on {self.day.isoformat()}"
        )


def available_methods(
    cylinder: Cylinder, facility: Facility, technician: Technician, day: date
) -> frozenset[Method]:
    """Everything all three of them agree on, for that day."""
    if not facility.approved_on(day) or not technician.qualified_on(day):
        return frozenset()
    return frozenset(
        method
        for method in permitted_methods(cylinder.specification, cylinder.service)
        if method in facility.methods and method in technician.methods
    )


def authorise(
    cylinder: Cylinder,
    facility: Facility,
    technician: Technician,
    method: Method,
    day: date,
) -> Authorisation:
    """Clear one method, or refuse with the reason that is worth acting on."""
    if not cylinder.status.accepts_work:
        raise RuleViolationError(
            f"{cylinder.key} is {cylinder.status.value} and takes no requalification", CITATION
        )
    require_permitted(cylinder.specification, cylinder.service, method)
    if not facility.approved_on(day):
        lapsed = facility.lapsed_by(day)
        detail = (
            f"lapsed {lapsed} days ago"
            if lapsed
            else f"not in force until {facility.approved_from.isoformat()}"
        )
        raise RuleViolationError(f"{facility.rin} is {detail}", CITATION)
    if method not in facility.methods:
        approved = ", ".join(sorted(item.value for item in facility.methods))
        raise RuleViolationError(
            f"{facility.rin} is not approved for {method.label}; it holds {approved}", CITATION
        )
    if not technician.qualified_on(day):
        raise RuleViolationError(
            f"{technician.badge} was not signed off on {day.isoformat()}", CITATION
        )
    if method not in technician.methods:
        raise RuleViolationError(
            f"{technician.badge} is not signed off for {method.label}", CITATION
        )
    return Authorisation(cylinder, facility, technician, method, day)


def choose_method(
    cylinder: Cylinder, facility: Facility, technician: Technician, day: date
) -> Method:
    """Pick the method the shop would use if nobody named one.

    A volumetric test is preferred wherever it is available because it is the
    only one that produces the expansion figures a star depends on. Anything
    else is a fallback, and a cylinder with no method at all is a refusal.
    """
    available = available_methods(cylinder, facility, technician, day)
    for preferred in (
        Method.VOLUMETRIC,
        Method.DIRECT_EXPANSION,
        Method.PROOF_PRESSURE,
        Method.ACETYLENE_VISUAL,
        Method.EXTERNAL_VISUAL,
        Method.ULTRASONIC,
    ):
        if preferred in available:
            return preferred
    raise RuleViolationError(
        f"nothing {facility.rin} and {technician.badge} hold covers {cylinder.key} "
        f"on {day.isoformat()}",
        CITATION,
    )
