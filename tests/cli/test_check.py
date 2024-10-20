import pytest

from .conftest import Invoke
from .test_endtoend import DAY, running_shop  # noqa: F401


@pytest.fixture
def condemned(running_shop: Invoke) -> Invoke:  # noqa: F811
    running_shop(
        "requal",
        "run",
        "NCI/A4471",
        "--tech",
        "jt7",
        "--system",
        "WJ-1",
        "--on",
        DAY,
        "--applied",
        "3358",
        "--total",
        "110.0",
        "--permanent",
        "2.0",
        "--defect",
        "bulge",
    )
    return running_shop


def test_a_clean_book_checks_out(running_shop: Invoke) -> None:  # noqa: F811
    assert "nothing to answer for" in running_shop("check").output


def test_a_warning_exits_eight(condemned: Invoke) -> None:
    result = condemned("check", "--on", "2024-06-13", expect=8)
    assert "has not been written to" in result.output


def test_warnings_can_be_waved_through(condemned: Invoke) -> None:
    condemned("check", "--on", "2024-06-13", "--warnings-are-fine")


def test_a_problem_exits_seven(condemned: Invoke) -> None:
    condemned("notice", "draft", "--on", "2024-06-13")
    result = condemned("check", "--on", "2024-07-20", "--warnings-are-fine", expect=7)
    assert "should have been written to" in result.output


def test_stats_on_an_empty_book(shop: Invoke) -> None:
    out = shop("stats").output
    assert "cylinders        0" in out
    assert "schema" in out


def test_stats_after_some_work(condemned: Invoke) -> None:
    out = condemned("stats").output
    assert "records of test  1" in out
    assert "condemned" in out
