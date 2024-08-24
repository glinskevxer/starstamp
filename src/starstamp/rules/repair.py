"""Which repairs a cylinder may have done to it.

The specification decides this and the decision is not symmetric. A welded
cylinder may be repaired by welding, because welding is how it was made. A
seamless cylinder may not, at any temperature, by anybody: an arc struck on a
seamless cylinder condemns it, and the shop that welds a bracket onto one has
destroyed it rather than repaired it.

Heat treatment runs the other way. Seamless steel can be normalised and put
back in service; high strength steel cannot, which is the reason its whole
service life is shorter.
"""

from __future__ import annotations

from datetime import date

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import Cylinder
from starstamp.model.repair import RepairKind
from starstamp.model.specification import SpecFamily
from starstamp.rules.interval import life_expired

CITATION = "49 CFR 180.211"

_ORDINARY = frozenset(
    {
        RepairKind.VALVE_REPLACEMENT,
        RepairKind.CLEANING,
        RepairKind.TUMBLING,
        RepairKind.PAINTING,
        RepairKind.FOOTRING_REPLACEMENT,
        RepairKind.REMARKING,
    }
)

_BY_FAMILY: dict[SpecFamily, frozenset[RepairKind]] = {
    SpecFamily.SEAMLESS_STEEL: _ORDINARY
    | {RepairKind.HEAT_TREATMENT, RepairKind.NECK_THREAD_REPAIR},
    SpecFamily.SEAMLESS_ALUMINUM: _ORDINARY | {RepairKind.NECK_THREAD_REPAIR},
    SpecFamily.WELDED_STEEL: _ORDINARY | {RepairKind.WELD_REPAIR, RepairKind.HEAT_TREATMENT},
    SpecFamily.HIGH_STRENGTH_STEEL: _ORDINARY,
    SpecFamily.ACETYLENE: frozenset(
        {RepairKind.VALVE_REPLACEMENT, RepairKind.PAINTING, RepairKind.REMARKING}
    ),
    SpecFamily.UN_ISO: _ORDINARY | {RepairKind.NECK_THREAD_REPAIR},
    SpecFamily.SPECIAL_PERMIT: frozenset({RepairKind.PAINTING, RepairKind.REMARKING}),
}


def permitted_repairs(cylinder: Cylinder) -> frozenset[RepairKind]:
    """Everything this cylinder may legally have done to it."""
    return _BY_FAMILY[cylinder.specification.family]


def require_permitted(cylinder: Cylinder, kind: RepairKind, day: date) -> RepairKind:
    """Check a repair against the cylinder, or say exactly why not."""
    if cylinder.status.is_terminal:
        raise RuleViolationError(
            f"{cylinder.key} is {cylinder.status.value} and is not repaired", CITATION
        )
    if life_expired(cylinder, day):
        raise RuleViolationError(
            f"{cylinder.key} is past its service life, so repairing it buys nothing", CITATION
        )
    allowed = permitted_repairs(cylinder)
    if kind in allowed:
        return kind
    if kind is RepairKind.WELD_REPAIR and cylinder.specification.is_seamless:
        raise RuleViolationError(
            f"{cylinder.specification} is seamless; an arc struck on it condemns it", CITATION
        )
    if kind is RepairKind.HEAT_TREATMENT:
        raise RuleViolationError(
            f"{cylinder.specification} is not heat treated back into service", CITATION
        )
    offered = ", ".join(sorted(item.value for item in allowed))
    raise RuleViolationError(
        f"{kind.label} is not done to {cylinder.specification}; it takes {offered}", CITATION
    )


def clears_a_suspension(kind: RepairKind) -> bool:
    """Whether this repair is the sort that lets a held cylinder move on.

    Painting a cylinder does not answer a suspension for damaged threads, so
    the caller still has to match the repair to what was found. What this
    answers is narrower: whether the repair is capable of clearing anything.
    """
    return kind is not RepairKind.PAINTING


def needs_requalification_after(kind: RepairKind) -> bool:
    return kind.needs_a_requalification_after
