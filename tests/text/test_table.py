import pytest

from starstamp.errors import ValidationError
from starstamp.text.table import dash, plural, render_pairs, render_table, yes_no


def test_table_aligns_columns() -> None:
    out = render_table(["code", "name"], [["A1", "Cascade"], ["LONGCODE", "Fire"]])
    lines = out.splitlines()
    assert lines[0] == "code      name"
    assert lines[1] == "--------  -------"
    assert lines[2] == "A1        Cascade"


def test_table_right_aligns_the_columns_it_is_told_to() -> None:
    out = render_table(["item", "cc"], [["a", "3"], ["b", "125"]], right=(1,))
    assert out.splitlines()[2].endswith("  3")


def test_table_refuses_a_ragged_row() -> None:
    with pytest.raises(ValidationError, match="row has 1 cells"):
        render_table(["a", "b"], [["only"]])


def test_table_with_no_rows_is_just_the_head() -> None:
    assert len(render_table(["a"], []).splitlines()) == 2


def test_pairs_line_up() -> None:
    out = render_pairs([("code", "A1"), ("longer label", "x")])
    assert out.splitlines()[0] == "code          A1"


def test_pairs_of_nothing() -> None:
    assert render_pairs([]) == ""


def test_small_helpers() -> None:
    assert yes_no(True) == "yes"
    assert yes_no(False) == "no"
    assert dash(None) == "-"
    assert dash(3) == "3"
    assert plural(1, "cylinder") == "1 cylinder"
    assert plural(2, "cylinder") == "2 cylinders"
    assert plural(0, "entry", "entries") == "0 entries"
