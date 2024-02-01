import pytest

from starstamp.errors import ValidationError
from starstamp.model.specification import SpecFamily, parse_specification
from starstamp.model.units import Pressure


@pytest.mark.parametrize(
    ("text", "code", "psig"),
    [
        ("DOT-3AA2015", "3AA", 2015),
        ("dot3aa2015", "3AA", 2015),
        ("3AA 2015", "3AA", 2015),
        ("DOT-3AL3000", "3AL", 3000),
        ("DOT 4BA240", "4BA", 240),
        ("DOT-3HT1850", "3HT", 1850),
        ("4BW240", "4BW", 240),
    ],
)
def test_parses_the_common_markings(text: str, code: str, psig: int) -> None:
    spec = parse_specification(text)
    assert spec.code == code
    assert spec.service_pressure == Pressure(psig)


def test_acetylene_has_no_service_pressure() -> None:
    spec = parse_specification("DOT-8AL")
    assert spec.family is SpecFamily.ACETYLENE
    assert spec.service_pressure is None
    assert not spec.carries_service_pressure
    with pytest.raises(ValidationError):
        spec.require_service_pressure()


def test_acetylene_marked_with_a_pressure_is_refused() -> None:
    with pytest.raises(ValidationError):
        parse_specification("DOT-8AL2015")


def test_a_pressure_bearing_spec_needs_its_pressure() -> None:
    with pytest.raises(ValidationError):
        parse_specification("DOT-3AA")


@pytest.mark.parametrize("text", ["DOT-SP 12345", "DOT-E12345", "SP-12345"])
def test_special_permits(text: str) -> None:
    spec = parse_specification(text)
    assert spec.family is SpecFamily.SPECIAL_PERMIT
    assert spec.permit_number == "12345"
    assert str(spec) == "DOT-SP 12345"


def test_un_iso() -> None:
    spec = parse_specification("UN ISO 9809-1")
    assert spec.family is SpecFamily.UN_ISO
    assert str(spec) == "UN ISO 9809-1"


@pytest.mark.parametrize("text", ["", "DOT-", "DOT-9ZZ2015", "banana"])
def test_junk_is_refused(text: str) -> None:
    with pytest.raises(ValidationError):
        parse_specification(text)


def test_family_predicates() -> None:
    steel = parse_specification("DOT-3AA2015")
    aluminum = parse_specification("DOT-3AL3000")
    welded = parse_specification("DOT-4BA240")
    assert steel.is_seamless
    assert steel.is_steel
    assert aluminum.is_seamless
    assert not aluminum.is_steel
    assert not welded.is_seamless
    assert welded.is_steel


def test_text_round_trip() -> None:
    assert str(parse_specification("dot 3aa2015")) == "DOT-3AA2015"
    assert str(parse_specification("DOT-8AL")) == "DOT-8AL"
