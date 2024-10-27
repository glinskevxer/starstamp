from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.service import ARGON, NITROGEN, OXYGEN, PROPANE
from starstamp.model.valve import CGA_540, CGA_580
from starstamp.rules.valve import (
    fitted_outlet,
    matches,
    refusal,
    require_matching,
    required_outlet,
    valve_for_a_service_change,
)

from ..support.factories import make_cylinder


def test_a_matching_valve() -> None:
    cylinder = make_cylinder(valve_outlet="580", valve_installed_on=date(2019, 4, 1))
    assert matches(cylinder, NITROGEN)
    assert refusal(cylinder, NITROGEN) is None
    assert require_matching(cylinder, NITROGEN) is CGA_580


def test_the_inert_gases_share_it() -> None:
    cylinder = make_cylinder(valve_outlet="580", valve_installed_on=date(2019, 4, 1))
    assert matches(cylinder, ARGON)


def test_the_wrong_valve_names_both_sides() -> None:
    cylinder = make_cylinder(valve_outlet="580", valve_installed_on=date(2019, 4, 1))
    assert refusal(cylinder, OXYGEN) == "the valve fitted is CGA 580 and oxygen takes CGA 540"
    with pytest.raises(RuleViolationError, match="takes CGA 540"):
        require_matching(cylinder, OXYGEN)


def test_an_unrecorded_valve_is_not_a_pass() -> None:
    bare = make_cylinder(valve_outlet=None, valve_installed_on=None)
    assert not matches(bare, NITROGEN)
    assert fitted_outlet(bare) is None
    assert "no valve outlet is recorded" in (refusal(bare, NITROGEN) or "")


def test_what_a_service_change_would_need() -> None:
    cylinder = make_cylinder(valve_outlet="580", valve_installed_on=date(2019, 4, 1))
    assert valve_for_a_service_change(cylinder, NITROGEN) is None
    assert valve_for_a_service_change(cylinder, OXYGEN) is CGA_540
    assert valve_for_a_service_change(cylinder, PROPANE) is not None


def test_the_outlet_a_gas_calls_for() -> None:
    assert required_outlet(OXYGEN) is CGA_540
