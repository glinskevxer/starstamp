import click
import pytest
from click.testing import CliRunner

from starstamp.cli.output import echo_count, echo_lines, echo_pairs, echo_table


def run(callback: object) -> str:
    @click.command()
    def command() -> None:
        callback()  # type: ignore[operator]

    return CliRunner().invoke(command).output


def test_a_table_prints_when_there_is_something() -> None:
    out = run(lambda: echo_table(["a", "b"], [["1", "2"]]))
    assert "a  b" in out
    assert "1  2" in out


def test_a_table_says_its_own_empty_line() -> None:
    out = run(lambda: echo_table(["a"], [], empty="nothing on the bench"))
    assert out.strip() == "nothing on the bench"


def test_a_table_reports_whether_it_printed() -> None:
    assert echo_table(["a"], [["1"]]) is True
    assert echo_table(["a"], []) is False


def test_pairs() -> None:
    out = run(lambda: echo_pairs([("code", "A1"), ("name", "x")]))
    assert "code  A1" in out


def test_lines_and_their_empty_case() -> None:
    assert "one" in run(lambda: echo_lines(["one", "two"]))
    assert "nothing" in run(lambda: echo_lines([], empty="nothing"))
    assert run(lambda: echo_lines([])) == ""


def test_counts_read_as_english() -> None:
    assert run(lambda: echo_count(1, "cylinder")).strip() == "1 cylinder"
    assert run(lambda: echo_count(2, "cylinder")).strip() == "2 cylinders"
    assert run(lambda: echo_count(0, "entry", "entries")).strip() == "0 entries"


@pytest.mark.parametrize("right", [(), (1,)])
def test_alignment_is_passed_through(right: tuple[int, ...]) -> None:
    out = run(lambda: echo_table(["a", "b"], [["1", "22"], ["3", "4"]], right=right))
    assert "22" in out
