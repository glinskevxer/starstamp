"""Whether the valve in the cylinder is the one the gas calls for.

The connection is the interlock, so this is a filling rule rather than a
requalification rule: a cylinder with the wrong valve is sound, requalified
and perfectly legal to own. It is only illegal to fill.
"""

from __future__ import annotations

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import Cylinder
from starstamp.model.service import GasService
from starstamp.model.valve import Outlet, outlet_for_service, parse_outlet

CITATION = "CGA V-1"


def required_outlet(service: GasService) -> Outlet:
    return outlet_for_service(service.code)


def fitted_outlet(cylinder: Cylinder) -> Outlet | None:
    if cylinder.valve_outlet is None:
        return None
    return parse_outlet(cylinder.valve_outlet)


def matches(cylinder: Cylinder, service: GasService) -> bool:
    """Whether what is fitted is what the gas takes. Unknown counts as no."""
    fitted = fitted_outlet(cylinder)
    if fitted is None:
        return False
    return fitted.number == required_outlet(service).number


def refusal(cylinder: Cylinder, service: GasService) -> str | None:
    """The refusal to put on a filling decision, or nothing."""
    fitted = fitted_outlet(cylinder)
    wanted = required_outlet(service)
    if fitted is None:
        return f"no valve outlet is recorded, and {service} takes {wanted}"
    if fitted.number != wanted.number:
        return f"the valve fitted is {fitted} and {service} takes {wanted}"
    return None


def require_matching(cylinder: Cylinder, service: GasService) -> Outlet:
    problem = refusal(cylinder, service)
    if problem is not None:
        raise RuleViolationError(f"{cylinder.key}: {problem}", CITATION)
    fitted = fitted_outlet(cylinder)
    assert fitted is not None
    return fitted


def valve_for_a_service_change(cylinder: Cylinder, service: GasService) -> Outlet | None:
    """The valve a cylinder would need to be put into another gas.

    Nothing if it already has the right one, which is the answer the counter
    wants when a customer asks to switch a cylinder from argon to oxygen.
    """
    if matches(cylinder, service):
        return None
    return required_outlet(service)
