from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from starstamp.errors import ValidationError
from starstamp.model.method import Method
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion, Pressure

PRESSURE = Pressure(3358)


def readings(**changes: object) -> PressureReadings:
    base: dict[str, object] = {
        "applied": PRESSURE,
        "hold_seconds": 30,
        "total_expansion": Expansion.parse("125.4"),
        "permanent_expansion": Expansion.parse("6.2"),
    }
    base.update(changes)
    return PressureReadings(**base)  # type: ignore[arg-type]


def test_elastic_expansion_is_the_difference() -> None:
    assert readings().elastic == Expansion.parse("119.2")


def test_permanent_percentage_is_exact() -> None:
    assert readings().permanent_percentage == Fraction(6200, 1254)


def test_expansion_comes_in_pairs() -> None:
    with pytest.raises(ValidationError, match="together or not at all"):
        readings(permanent_expansion=None)
    with pytest.raises(ValidationError, match="together or not at all"):
        readings(total_expansion=None)


def test_transposed_readings_are_caught() -> None:
    with pytest.raises(ValidationError, match="transposed"):
        readings(
            total_expansion=Expansion.parse("6.2"), permanent_expansion=Expansion.parse("125.4")
        )


def test_a_total_of_zero_is_not_a_reading() -> None:
    with pytest.raises(ValidationError, match="not a reading from a rig"):
        readings(total_expansion=Expansion(0), permanent_expansion=Expansion(0))


def test_a_negative_hold_is_refused() -> None:
    with pytest.raises(ValidationError, match="cannot be negative"):
        readings(hold_seconds=-1)


def test_the_hold_time_floor() -> None:
    assert readings(hold_seconds=30).held_long_enough
    assert not readings(hold_seconds=29).held_long_enough


def test_a_proof_pressure_record_carries_no_expansion() -> None:
    proof = PressureReadings(applied=PRESSURE, hold_seconds=30)
    assert not proof.has_expansion
    with pytest.raises(ValidationError, match="no total expansion"):
        _ = proof.total
    with pytest.raises(ValidationError, match="no permanent expansion"):
        _ = proof.permanent


def test_readings_have_to_match_the_method() -> None:
    volumetric = readings()
    proof = PressureReadings(applied=PRESSURE, hold_seconds=30)
    assert volumetric.suits(Method.VOLUMETRIC)
    assert not volumetric.suits(Method.PROOF_PRESSURE)
    assert proof.suits(Method.PROOF_PRESSURE)
    assert not proof.suits(Method.VOLUMETRIC)


def test_requiring_the_wrong_shape_says_which_way_round_it_is() -> None:
    with pytest.raises(ValidationError, match="needs total and permanent"):
        PressureReadings(applied=PRESSURE, hold_seconds=30).require_for(Method.VOLUMETRIC)
    with pytest.raises(ValidationError, match="belong to another method"):
        readings().require_for(Method.PROOF_PRESSURE)


def test_a_visual_method_never_reaches_the_rig() -> None:
    with pytest.raises(ValidationError, match="does not put the cylinder on a rig"):
        readings().require_for(Method.EXTERNAL_VISUAL)


def test_describe_reads_like_the_record_of_test() -> None:
    line = readings(leaked=True, distorted=True).describe()
    assert line == (
        "3358 psig, held 30s, total 125.4 cc, permanent 6.2 cc, leaked, visibly distorted"
    )


def test_describe_of_a_proof_test() -> None:
    assert PressureReadings(applied=PRESSURE, hold_seconds=45).describe() == "3358 psig, held 45s"


@given(
    total=st.integers(min_value=1, max_value=100_000),
    permanent=st.integers(min_value=0, max_value=100_000),
)
def test_the_percentage_never_exceeds_a_hundred(total: int, permanent: int) -> None:
    if permanent > total:
        permanent, total = total, permanent
    if total == 0:
        return
    pair = PressureReadings(
        applied=PRESSURE,
        hold_seconds=30,
        total_expansion=Expansion(total),
        permanent_expansion=Expansion(permanent),
    )
    assert 0 <= pair.permanent_percentage <= 100
    assert pair.elastic.tenths_cc == total - permanent
