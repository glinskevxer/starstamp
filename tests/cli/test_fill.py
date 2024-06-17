import pytest

from .conftest import Invoke
from .test_endtoend import DAY, running_shop  # noqa: F401


@pytest.fixture
def tested(running_shop: Invoke) -> Invoke:  # noqa: F811
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
    )
    return running_shop


def test_a_tested_cylinder_may_be_filled(tested: Invoke) -> None:
    out = tested("--today", "2024-07-01", "fill", "check", "NCI/A4471").output
    assert "may be filled with nitrogen" in out
    assert "due 06-34" in out


def test_the_plus_rating_shows_in_the_ceiling(tested: Invoke) -> None:
    out = tested("--today", "2024-07-01", "fill", "check", "NCI/A4471").output
    assert "2217 psig" in out


def test_a_gas_that_needs_its_own_cylinder_is_refused(tested: Invoke) -> None:
    result = tested("--today", "2024-07-01", "fill", "check", "NCI/A4471", "--gas", "NH3", expect=6)
    assert "needs a cylinder dedicated to it" in result.output


def test_an_untested_cylinder_is_refused(running_shop: Invoke) -> None:  # noqa: F811
    result = running_shop("--today", "2024-07-01", "fill", "check", "NCI/A4471", expect=6)
    assert "no standing requalification" in result.output


def test_the_due_list(tested: Invoke) -> None:
    out = tested("--today", "2034-04-01", "fill", "due", "--within", "3").output
    assert "NCI/A4471" in out
    assert "06-34" in out


def test_nothing_due(tested: Invoke) -> None:
    assert "nothing due" in tested("--today", "2025-01-01", "fill", "due").output


def test_the_due_list_by_owner(tested: Invoke) -> None:
    out = tested("--today", "2034-04-01", "fill", "due", "--owner", "weld1").output
    assert "WELD1" in out
