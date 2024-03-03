import pytest

from starstamp.errors import ValidationError
from starstamp.model.method import Method


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("volumetric", Method.VOLUMETRIC),
        ("water jacket", Method.VOLUMETRIC),
        ("WJ", Method.VOLUMETRIC),
        ("direct-expansion", Method.DIRECT_EXPANSION),
        ("proof", Method.PROOF_PRESSURE),
        ("visual", Method.EXTERNAL_VISUAL),
        ("ut", Method.ULTRASONIC),
        ("acetylene", Method.ACETYLENE_VISUAL),
    ],
)
def test_parses_the_shop_shorthand(text: str, expected: Method) -> None:
    assert Method.parse(text) is expected


def test_an_unknown_method_lists_what_is_performed() -> None:
    with pytest.raises(ValidationError, match="the shop performs"):
        Method.parse("x ray")


def test_only_two_methods_measure_expansion() -> None:
    measuring = {method for method in Method if method.measures_expansion}
    assert measuring == {Method.VOLUMETRIC, Method.DIRECT_EXPANSION}


def test_proof_pressure_is_a_pressure_test_that_measures_nothing() -> None:
    assert Method.PROOF_PRESSURE.is_pressure_test
    assert not Method.PROOF_PRESSURE.measures_expansion


def test_visual_methods_are_not_pressure_tests() -> None:
    assert not Method.EXTERNAL_VISUAL.is_pressure_test
    assert not Method.ACETYLENE_VISUAL.is_pressure_test
    assert not Method.ULTRASONIC.is_pressure_test


def test_only_the_water_jacket_needs_a_jacket() -> None:
    assert Method.VOLUMETRIC.needs_water_jacket
    assert not Method.DIRECT_EXPANSION.needs_water_jacket


def test_labels_read_as_words() -> None:
    assert Method.PROOF_PRESSURE.label == "proof pressure"
