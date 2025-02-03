"""Properties of the two calendars, which the intervals rest on."""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from starstamp.model.dates import StampedMonth
from starstamp.rules.interval import is_out_of_test, months_remaining

years = st.integers(min_value=1950, max_value=2100)
# The window is deliberately inside what a stamped month accepts: the point of
# these properties is the arithmetic, not the bounds check, which has its own test.
months = st.integers(min_value=1, max_value=12)
intervals = st.integers(min_value=0, max_value=30)


@given(year=years, month=months, count=intervals)
def test_adding_years_keeps_the_month(year: int, month: int, count: int) -> None:
    stamped = StampedMonth(year, month)
    moved = stamped.plus_years(count)
    assert moved.month == stamped.month
    assert moved.year == stamped.year + count


@given(year=st.integers(1990, 2060), month=months, count=st.integers(-240, 240))
def test_months_and_their_inverse(year: int, month: int, count: int) -> None:
    stamped = StampedMonth(year, month)
    moved = stamped.plus_months(count)
    assert stamped.months_until(moved) == count
    assert moved.plus_months(-count) == stamped


@given(year=st.integers(1951, 2099), month=months)
def test_a_month_covers_its_own_days_and_no_others(year: int, month: int) -> None:
    stamped = StampedMonth(year, month)
    first, last = stamped.first_day(), stamped.last_day()
    assert stamped.contains(first)
    assert stamped.contains(last)
    assert not stamped.contains(first - timedelta(days=1))
    assert not stamped.contains(last + timedelta(days=1))


@given(year=st.integers(1951, 2099), month=months)
def test_out_of_test_starts_the_day_after_the_month_ends(year: int, month: int) -> None:
    due = StampedMonth(year, month)
    assert not is_out_of_test(due, due.last_day())
    assert is_out_of_test(due, due.last_day() + timedelta(days=1))


@given(year=st.integers(1990, 2060), month=months, offset=st.integers(-60, 60))
def test_months_remaining_matches_the_month_arithmetic(year: int, month: int, offset: int) -> None:
    due = StampedMonth(year, month)
    day: date = due.plus_months(offset).first_day()
    assert months_remaining(due, day) == -offset
