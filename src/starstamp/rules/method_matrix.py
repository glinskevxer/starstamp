"""Which methods a cylinder may be requalified by, and at what pressure.

Two decisions live here and they are not independent. The specification says
which methods are on the table, the gas narrows that further, and the
specification then decides the multiplier that turns service pressure into
test pressure. A shop that gets the multiplier from the method instead of the
specification will test a welded cylinder to five thirds and pass a cylinder
that should have failed.
"""

from __future__ import annotations

from fractions import Fraction

from starstamp.errors import RuleViolationError
from starstamp.model.method import Method
from starstamp.model.service import GasService
from starstamp.model.specification import SpecFamily, Specification
from starstamp.model.units import Pressure

_BY_FAMILY: dict[SpecFamily, frozenset[Method]] = {
    SpecFamily.SEAMLESS_STEEL: frozenset({Method.VOLUMETRIC, Method.DIRECT_EXPANSION}),
    SpecFamily.SEAMLESS_ALUMINUM: frozenset(
        {Method.VOLUMETRIC, Method.DIRECT_EXPANSION, Method.ULTRASONIC}
    ),
    SpecFamily.WELDED_STEEL: frozenset(
        {Method.VOLUMETRIC, Method.PROOF_PRESSURE, Method.EXTERNAL_VISUAL}
    ),
    SpecFamily.HIGH_STRENGTH_STEEL: frozenset({Method.VOLUMETRIC}),
    SpecFamily.ACETYLENE: frozenset({Method.ACETYLENE_VISUAL}),
    SpecFamily.UN_ISO: frozenset({Method.VOLUMETRIC, Method.PROOF_PRESSURE}),
    SpecFamily.SPECIAL_PERMIT: frozenset(),
}

_TEST_PRESSURE_FACTOR: dict[SpecFamily, Fraction] = {
    SpecFamily.SEAMLESS_STEEL: Fraction(5, 3),
    SpecFamily.SEAMLESS_ALUMINUM: Fraction(5, 3),
    SpecFamily.HIGH_STRENGTH_STEEL: Fraction(5, 3),
    SpecFamily.WELDED_STEEL: Fraction(2, 1),
    SpecFamily.UN_ISO: Fraction(3, 2),
}

CITATION = "49 CFR 180.209"


def permitted_methods(specification: Specification, service: GasService) -> frozenset[Method]:
    """Every method this cylinder in this gas may be requalified by.

    The external visual alone is the narrow one: it exists for welded
    cylinders in a dedicated service, and offering it to a welded cylinder in
    a shared service is the mistake this function exists to prevent.
    """
    allowed = set(_BY_FAMILY[specification.family])
    if Method.EXTERNAL_VISUAL in allowed and not service.requires_dedicated_cylinder:
        allowed.discard(Method.EXTERNAL_VISUAL)
    if Method.ULTRASONIC in allowed and not service.is_dry_service:
        allowed.discard(Method.ULTRASONIC)
    return frozenset(allowed)


def require_permitted(specification: Specification, service: GasService, method: Method) -> Method:
    """Check a method against the cylinder, or say exactly why not."""
    allowed = permitted_methods(specification, service)
    if method in allowed:
        return method
    if not allowed:
        raise RuleViolationError(
            f"{specification} carries no method the shop may perform without the permit terms",
            CITATION,
        )
    offered = ", ".join(sorted(item.value for item in allowed))
    raise RuleViolationError(
        f"{method.label} is not permitted for {specification} in {service}; "
        f"this cylinder takes {offered}",
        CITATION,
    )


def pressure_factor(specification: Specification) -> Fraction:
    """The multiplier from service pressure to test pressure."""
    factor = _TEST_PRESSURE_FACTOR.get(specification.family)
    if factor is None:
        raise RuleViolationError(
            f"{specification} has no test pressure the shop can derive", CITATION
        )
    return factor


def required_test_pressure(specification: Specification) -> Pressure:
    """The pressure this cylinder is tested to.

    The factor is looked up before the service pressure, so a cylinder that is
    never pressure tested at all reports that rather than complaining about a
    marking it was never given.
    """
    factor = pressure_factor(specification)
    if specification.service_pressure is None:
        # A UN marking carries a test pressure of its own rather than a
        # service pressure, and the shop reads that off the cylinder. Until it
        # is recorded there is nothing here to derive from.
        raise RuleViolationError(
            f"{specification} carries no service pressure to derive a test pressure from",
            CITATION,
        )
    return specification.service_pressure.scaled(factor)


def methods_requiring_expansion(
    specification: Specification, service: GasService
) -> frozenset[Method]:
    return frozenset(
        method for method in permitted_methods(specification, service) if method.measures_expansion
    )
