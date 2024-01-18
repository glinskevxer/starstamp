from fractions import Fraction

import pytest

from starstamp.errors import ValidationError
from starstamp.model.units import Expansion, Pressure


def test_pressure_parses_bare_digits() -> None:
    assert Pressure.parse("2015") == Pressure(2015)


@pytest.mark.parametrize("text", ["2015 psi", " 2015psig", "2015 PSIG "])
def test_pressure_parses_stamped_forms(text: str) -> None:
    assert Pressure.parse(text).psig == 2015


@pytest.mark.parametrize("text", ["", "2015.5", "two thousand", "-40"])
def test_pressure_rejects_junk(text: str) -> None:
    with pytest.raises(ValidationError):
        Pressure.parse(text)


def test_pressure_refuses_negative() -> None:
    with pytest.raises(ValidationError):
        Pressure(-1)


def test_pressure_scales_five_thirds_rounding_half_up() -> None:
    # 2015 * 5/3 is 3358.33, and the test pressure stamped is 3360 by the
    # manufacturer, so the shop rounds its own derivation to whole psi.
    assert Pressure(2015).scaled(Fraction(5, 3)) == Pressure(3358)
    assert Pressure(3).scaled(Fraction(1, 2)) == Pressure(2)


def test_pressure_orders() -> None:
    assert Pressure(2015) < Pressure(2265)
    assert max([Pressure(1800), Pressure(2400)]) == Pressure(2400)


def test_expansion_parses_tenths() -> None:
    assert Expansion.parse("125.4").tenths_cc == 1254
    assert Expansion.parse("125").tenths_cc == 1250


def test_expansion_rejects_hundredths() -> None:
    with pytest.raises(ValidationError):
        Expansion.parse("125.44")


def test_expansion_ratio_is_exact() -> None:
    total = Expansion.parse("125.4")
    permanent = Expansion.parse("12.5")
    assert permanent.ratio_to(total) == Fraction(125, 1254)


def test_expansion_ratio_refuses_zero_denominator() -> None:
    with pytest.raises(ValidationError):
        Expansion.parse("1.0").ratio_to(Expansion(0))


def test_expansion_text() -> None:
    assert str(Expansion.parse("125.4")) == "125.4 cc"
    assert str(Pressure(2015)) == "2015 psig"
