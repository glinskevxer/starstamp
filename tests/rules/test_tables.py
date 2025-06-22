"""The rule tables, walked in full rather than sampled.

Each of these rules is a table with a handful of entries, and the entries are
the sort of thing that gets edited by somebody adding a specification and not
noticing what else keys off it. Walking the whole cross product is cheap and
it is the only way a missing entry shows up as a failure rather than as a
KeyError in front of a customer.
"""

from __future__ import annotations

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.defect import DefectKind, Observation
from starstamp.model.method import Method
from starstamp.model.service import GasService, all_services
from starstamp.model.specification import Specification, parse_specification
from starstamp.rules.method_matrix import (
    permitted_methods,
    pressure_factor,
    required_test_pressure,
)
from starstamp.rules.repair import permitted_repairs
from starstamp.rules.validity import required_instruments
from starstamp.rules.valve import required_outlet
from starstamp.rules.visual import VisualResult, judge

from ..support.factories import make_cylinder

SPECS = (
    "DOT-3A2015",
    "DOT-3AA2015",
    "DOT-3AA2265",
    "DOT-3AL3000",
    "DOT-3HT1850",
    "DOT-4B240",
    "DOT-4BA240",
    "DOT-4BW240",
    "DOT-8AL",
    "DOT-SP 14456",
    "UN ISO 9809-1",
)


def specs() -> list[Specification]:
    return [parse_specification(text) for text in SPECS]


@pytest.mark.parametrize("spec_text", SPECS)
def test_every_specification_answers_the_method_matrix(spec_text: str) -> None:
    spec = parse_specification(spec_text)
    for service in all_services():
        allowed = permitted_methods(spec, service)
        assert isinstance(allowed, frozenset)


@pytest.mark.parametrize("spec_text", SPECS)
def test_every_specification_answers_the_repair_table(spec_text: str) -> None:
    cylinder = make_cylinder(
        specification=parse_specification(spec_text), rejection_elastic_expansion=None
    )
    assert permitted_repairs(cylinder)


DERIVABLE = {
    "DOT-3A2015",
    "DOT-3AA2015",
    "DOT-3AA2265",
    "DOT-3AL3000",
    "DOT-3HT1850",
    "DOT-4B240",
    "DOT-4BA240",
    "DOT-4BW240",
}


@pytest.mark.parametrize("spec_text", sorted(DERIVABLE))
def test_a_marked_service_pressure_gives_a_test_pressure(spec_text: str) -> None:
    spec = parse_specification(spec_text)
    assert required_test_pressure(spec).psig > 0
    assert pressure_factor(spec) > 1


@pytest.mark.parametrize("spec_text", sorted(set(SPECS) - DERIVABLE))
def test_the_rest_refuse_by_name(spec_text: str) -> None:
    spec = parse_specification(spec_text)
    with pytest.raises(RuleViolationError, match="no service pressure|no test pressure"):
        required_test_pressure(spec)


@pytest.mark.parametrize("method", list(Method))
def test_every_method_says_which_instruments_it_needs(method: Method) -> None:
    instruments = required_instruments(method)
    if method.is_pressure_test:
        assert instruments
    assert isinstance(instruments, frozenset)


@pytest.mark.parametrize("service", all_services(), ids=lambda item: item.code)
def test_every_gas_has_an_outlet_and_a_hazard(service: GasService) -> None:
    assert required_outlet(service)
    assert service.hazard.value


@pytest.mark.parametrize("kind", list(DefectKind))
def test_every_defect_can_be_judged(kind: DefectKind) -> None:
    """No defect kind falls through the visual rules with a KeyError."""
    observation = Observation(
        kind=kind,
        depth_thousandths_in=10 if kind.is_measured_by_depth else None,
        length_thousandths_in=4000 if kind.wants_a_length else None,
    )
    if kind is DefectKind.DENT:
        observation = Observation(kind=kind, depth_thousandths_in=10, length_thousandths_in=4000)
    finding = judge(observation, parse_specification("DOT-3AA2015"), 220)
    assert finding.result in set(VisualResult)
    assert finding.reason


@pytest.mark.parametrize("spec_text", SPECS)
def test_an_acetylene_cylinder_is_the_only_one_with_no_pressure_method(
    spec_text: str,
) -> None:
    from starstamp.model.service import NITROGEN
    from starstamp.model.specification import SpecFamily

    spec = parse_specification(spec_text)
    allowed = permitted_methods(spec, NITROGEN)
    pressure_methods = {method for method in allowed if method.is_pressure_test}
    if spec.family in {SpecFamily.ACETYLENE, SpecFamily.SPECIAL_PERMIT}:
        assert not pressure_methods
    else:
        assert pressure_methods


def test_the_dry_services_are_the_ones_a_star_can_rest_on() -> None:
    dry = {service.code for service in all_services() if service.is_dry_service}
    assert "N2" in dry
    assert "NH3" not in dry
    assert "CL2" not in dry


@pytest.mark.parametrize("spec_text", SPECS)
def test_the_specification_round_trips_through_its_text(spec_text: str) -> None:
    spec = parse_specification(spec_text)
    assert parse_specification(str(spec)) == spec
