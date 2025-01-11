from datetime import date

import pytest

from starstamp.cli.windows import Window, parse_month, resolve
from starstamp.errors import ValidationError
from starstamp.model.dates import StampedMonth

TODAY = date(2024, 6, 12)


def test_a_window_that_ends_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="ends after it starts"):
        Window(date(2024, 6, 30), date(2024, 6, 1))


def test_a_window_counts_both_ends() -> None:
    window = Window(date(2024, 6, 1), date(2024, 6, 30))
    assert window.days == 30
    assert window.contains(date(2024, 6, 1))
    assert window.contains(date(2024, 6, 30))
    assert not window.contains(date(2024, 7, 1))
    assert str(window) == "2024-06-01 to 2024-06-30"


def test_a_single_day_window() -> None:
    assert Window(TODAY, TODAY).days == 1


def test_months_parse() -> None:
    assert parse_month(" 2024-06 ") == StampedMonth(2024, 6)


@pytest.mark.parametrize("text", ["2024", "june", "2024/06", ""])
def test_bad_months(text: str) -> None:
    with pytest.raises(ValidationError, match="a month is YYYY-MM"):
        parse_month(text)


def test_a_named_month_wins() -> None:
    window = resolve(TODAY, month="2024-03", first="2024-01-01", last="2024-01-31")
    assert window.first == date(2024, 3, 1)
    assert window.last == date(2024, 3, 31)


def test_a_pair_of_days() -> None:
    window = resolve(TODAY, first="2024-01-01", last="2024-02-15")
    assert window.days == 46


def test_a_first_day_alone_runs_to_today() -> None:
    assert resolve(TODAY, first="2024-06-01").last == TODAY


def test_a_last_day_alone_starts_at_its_month() -> None:
    window = resolve(TODAY, last="2024-04-20")
    assert window.first == date(2024, 4, 1)
    assert window.last == date(2024, 4, 20)


def test_the_fallback_is_this_month() -> None:
    window = resolve(TODAY)
    assert window.first == date(2024, 6, 1)
    assert window.last == date(2024, 6, 30)


def test_a_backwards_pair_is_refused() -> None:
    with pytest.raises(ValidationError, match="ends after it starts"):
        resolve(TODAY, first="2024-06-30", last="2024-06-01")
