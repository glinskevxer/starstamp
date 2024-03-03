from fractions import Fraction

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.method import Method
from starstamp.model.service import AMMONIA, NITROGEN, OXYGEN, PROPANE
from starstamp.model.specification import parse_specification
from starstamp.rules.method_matrix import (
    methods_requiring_expansion,
    permitted_methods,
    pressure_factor,
    require_permitted,
    required_test_pressure,
)

SEAMLESS = parse_specification("DOT-3AA2015")
ALUMINUM = parse_specification("DOT-3AL3000")
WELDED = parse_specification("DOT-4BA240")
HIGH_STRENGTH = parse_specification("DOT-3HT1850")
ACETYLENE_SPEC = parse_specification("DOT-8AL")
PERMIT = parse_specification("DOT-SP 14456")


def test_seamless_steel_takes_the_two_expansion_methods() -> None:
    assert permitted_methods(SEAMLESS, NITROGEN) == frozenset(
        {Method.VOLUMETRIC, Method.DIRECT_EXPANSION}
    )


def test_high_strength_steel_takes_the_water_jacket_only() -> None:
    assert permitted_methods(HIGH_STRENGTH, OXYGEN) == frozenset({Method.VOLUMETRIC})


def test_acetylene_is_never_pressure_tested() -> None:
    allowed = permitted_methods(ACETYLENE_SPEC, NITROGEN)
    assert allowed == frozenset({Method.ACETYLENE_VISUAL})
    assert not any(method.is_pressure_test for method in allowed)


def test_the_external_visual_needs_a_dedicated_service() -> None:
    assert Method.EXTERNAL_VISUAL in permitted_methods(WELDED, AMMONIA)
    assert Method.EXTERNAL_VISUAL not in permitted_methods(WELDED, NITROGEN)
    assert Method.EXTERNAL_VISUAL in permitted_methods(WELDED, PROPANE)


def test_ultrasound_is_off_the_table_in_a_wet_service() -> None:
    assert Method.ULTRASONIC in permitted_methods(ALUMINUM, NITROGEN)
    assert Method.ULTRASONIC not in permitted_methods(ALUMINUM, AMMONIA)


def test_a_permitted_method_comes_back() -> None:
    assert require_permitted(SEAMLESS, NITROGEN, Method.VOLUMETRIC) is Method.VOLUMETRIC


def test_a_refusal_names_what_the_cylinder_does_take() -> None:
    with pytest.raises(RuleViolationError) as caught:
        require_permitted(SEAMLESS, NITROGEN, Method.PROOF_PRESSURE)
    message = str(caught.value)
    assert "proof pressure is not permitted" in message
    assert "direct_expansion, volumetric" in message
    assert "180.209" in message


def test_a_special_permit_has_no_matrix_of_its_own() -> None:
    assert permitted_methods(PERMIT, NITROGEN) == frozenset()
    with pytest.raises(RuleViolationError, match="permit terms"):
        require_permitted(PERMIT, NITROGEN, Method.VOLUMETRIC)


def test_the_multiplier_comes_from_the_specification() -> None:
    assert pressure_factor(SEAMLESS) == Fraction(5, 3)
    assert pressure_factor(WELDED) == Fraction(2, 1)


def test_derived_test_pressures() -> None:
    assert required_test_pressure(SEAMLESS).psig == 3358
    assert required_test_pressure(WELDED).psig == 480
    assert required_test_pressure(ALUMINUM).psig == 5000


def test_a_permit_has_no_derivable_test_pressure() -> None:
    with pytest.raises(RuleViolationError, match="no test pressure"):
        pressure_factor(PERMIT)


def test_acetylene_has_no_test_pressure_to_derive() -> None:
    with pytest.raises(RuleViolationError, match="no test pressure"):
        required_test_pressure(ACETYLENE_SPEC)


def test_methods_requiring_expansion_narrows_to_the_measuring_ones() -> None:
    assert methods_requiring_expansion(WELDED, AMMONIA) == frozenset({Method.VOLUMETRIC})
    assert methods_requiring_expansion(ACETYLENE_SPEC, NITROGEN) == frozenset()
