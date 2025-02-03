"""Properties the arithmetic has to hold whatever the numbers are.

These exist because the shop's decisions are comparisons, and a comparison is
only as good as the arithmetic under it. Each property here is one that would
be violated by the obvious floating point implementation of the same rule.
"""

from __future__ import annotations

from fractions import Fraction

from hypothesis import assume, given
from hypothesis import strategies as st

from starstamp.model.money import Money, total
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion, Pressure

cents = st.integers(min_value=0, max_value=10_000_000)
tenths = st.integers(min_value=1, max_value=1_000_000)
psi = st.integers(min_value=0, max_value=15_000)


@given(first=cents, second=cents)
def test_money_addition_is_exact(first: int, second: int) -> None:
    assert Money(first).plus(Money(second)).cents == first + second


@given(amount=cents, count=st.integers(min_value=0, max_value=500))
def test_multiplying_money_never_loses_a_cent(amount: int, count: int) -> None:
    assert Money(amount).times(count).cents == amount * count


@given(amount=cents, denominator=st.integers(min_value=1, max_value=12))
def test_shares_add_back_to_within_a_cent(amount: int, denominator: int) -> None:
    money = Money(amount)
    shares = [money.share_of(1, denominator) for _ in range(denominator)]
    rebuilt = total(shares)
    assert abs(rebuilt.cents - amount) <= denominator


@given(text=st.decimals(min_value=0, max_value=99999, places=2, allow_nan=False))
def test_money_round_trips_through_text(text: object) -> None:
    parsed = Money.parse(str(text))
    assert Money.parse(str(parsed)) == parsed


@given(value=psi, numerator=st.integers(1, 12), denominator=st.integers(1, 12))
def test_scaling_a_pressure_stays_within_half_a_psi(
    value: int, numerator: int, denominator: int
) -> None:
    factor = Fraction(numerator, denominator)
    scaled = Pressure(value).scaled(factor)
    exact = Fraction(value) * factor
    assert abs(Fraction(scaled.psig) - exact) <= Fraction(1, 2)


@given(total_cc=tenths, permanent_cc=tenths)
def test_expansion_readings_are_ordered_or_refused(total_cc: int, permanent_cc: int) -> None:
    assume(permanent_cc <= total_cc)
    readings = PressureReadings(
        applied=Pressure(3358),
        hold_seconds=30,
        total_expansion=Expansion(total_cc),
        permanent_expansion=Expansion(permanent_cc),
    )
    assert readings.elastic.tenths_cc + permanent_cc == total_cc
    assert 0 <= readings.permanent_percentage <= 100


@given(total_cc=tenths, permanent_cc=tenths)
def test_the_percentage_is_monotonic_in_the_permanent_reading(
    total_cc: int, permanent_cc: int
) -> None:
    assume(permanent_cc + 1 <= total_cc)
    lower = PressureReadings(
        applied=Pressure(3358),
        hold_seconds=30,
        total_expansion=Expansion(total_cc),
        permanent_expansion=Expansion(permanent_cc),
    )
    higher = PressureReadings(
        applied=Pressure(3358),
        hold_seconds=30,
        total_expansion=Expansion(total_cc),
        permanent_expansion=Expansion(permanent_cc + 1),
    )
    assert higher.permanent_percentage > lower.permanent_percentage


@given(value=st.integers(min_value=0, max_value=1_000_000))
def test_expansion_round_trips_through_text(value: int) -> None:
    expansion = Expansion(value)
    assert Expansion.parse(str(expansion).removesuffix(" cc")) == expansion
