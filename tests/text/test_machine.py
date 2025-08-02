from datetime import date
from fractions import Fraction

from starstamp.text import machine


def test_dates_and_fractions_come_out_readable() -> None:
    assert machine.encode(date(2024, 6, 12)) == "2024-06-12"
    assert machine.encode(Fraction(1, 2)) == 0.5


def test_containers_are_walked() -> None:
    assert machine.encode([date(2024, 6, 12)]) == ["2024-06-12"]
    assert machine.encode({"a": Fraction(3, 4)}) == {"a": 0.75}
    assert machine.encode({date(2024, 6, 12)}) == ["2024-06-12"]


def test_plain_values_pass_through() -> None:
    assert machine.encode(3) == 3
    assert machine.encode("x") == "x"
    assert machine.encode(None) is None


def test_anything_with_an_isoformat_is_taken_as_a_time() -> None:
    class Odd:
        def isoformat(self) -> str:
            return "2024-06-12T08:00:00"

    assert machine.encode(Odd()) == "2024-06-12T08:00:00"


def test_the_dump_is_sorted_and_indented() -> None:
    text = machine.dumps({"b": 1, "a": 2})
    assert text.splitlines()[1].strip().startswith('"a"')
    assert "  " in text
