from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.dates import StampedMonth, parse_day


def test_parse_day_reads_iso() -> None:
    assert parse_day(" 2025-03-04 ") == date(2025, 3, 4)


@pytest.mark.parametrize("text", ["2025/03/04", "3-4-2025", "20250304", ""])
def test_parse_day_rejects_other_shapes(text: str) -> None:
    with pytest.raises(ValidationError):
        parse_day(text)


def test_parse_day_rejects_impossible_day() -> None:
    with pytest.raises(ValidationError):
        parse_day("2025-02-30")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("7-24", StampedMonth(2024, 7)),
        ("07/24", StampedMonth(2024, 7)),
        ("07-2024", StampedMonth(2024, 7)),
        ("12 1998", StampedMonth(1998, 12)),
        ("3/85", StampedMonth(1985, 3)),
    ],
)
def test_stamped_month_parses_the_marked_forms(text: str, expected: StampedMonth) -> None:
    assert StampedMonth.parse(text) == expected


def test_two_digit_year_window_splits_at_seventy_nine() -> None:
    assert StampedMonth.parse("1-79").year == 2079
    assert StampedMonth.parse("1-80").year == 1980


@pytest.mark.parametrize("text", ["13-24", "0-24", "july 24", "2024-07"])
def test_stamped_month_rejects_junk(text: str) -> None:
    with pytest.raises(ValidationError):
        StampedMonth.parse(text)


def test_month_bounds() -> None:
    month = StampedMonth(2024, 2)
    assert month.first_day() == date(2024, 2, 1)
    assert month.last_day() == date(2024, 2, 29)


def test_plus_years_keeps_the_month() -> None:
    assert StampedMonth(2020, 2).plus_years(5) == StampedMonth(2025, 2)


def test_plus_years_refuses_negative() -> None:
    with pytest.raises(ValidationError):
        StampedMonth(2020, 2).plus_years(-1)


def test_plus_months_rolls_the_year() -> None:
    assert StampedMonth(2024, 11).plus_months(3) == StampedMonth(2025, 2)
    assert StampedMonth(2024, 1).plus_months(0) == StampedMonth(2024, 1)


def test_months_until_is_signed() -> None:
    assert StampedMonth(2024, 1).months_until(StampedMonth(2025, 1)) == 12
    assert StampedMonth(2025, 1).months_until(StampedMonth(2024, 1)) == -12


def test_contains_a_day() -> None:
    month = StampedMonth(2025, 3)
    assert month.contains(date(2025, 3, 31))
    assert not month.contains(date(2025, 4, 1))


def test_text_forms() -> None:
    assert str(StampedMonth(2024, 7)) == "07-24"
    assert StampedMonth(2024, 7).long_form() == "2024-07"


def test_months_order() -> None:
    assert StampedMonth(2024, 11) < StampedMonth(2024, 12) < StampedMonth(2025, 1)
