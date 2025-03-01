import pytest

from .conftest import DAY, Invoke


@pytest.fixture
def tested(running_shop: Invoke) -> Invoke:
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


def test_an_untested_cylinder_is_refused(running_shop: Invoke) -> None:
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


def test_recording_a_fill(tested: Invoke) -> None:
    out = tested(
        "fill", "record", "NCI/A4471", "--by", "jt7", "--to", "2015", "--on", "2024-06-20"
    ).output
    assert "NCI/A4471 nitrogen 2015 psig at 70F" in out


def test_a_fill_the_shop_would_refuse(running_shop: Invoke) -> None:
    result = running_shop(
        "fill",
        "record",
        "NCI/A4471",
        "--by",
        "jt7",
        "--to",
        "2015",
        "--on",
        "2024-06-20",
        expect=5,
    )
    assert "may not be filled" in result.output


def test_recording_it_anyway(running_shop: Invoke) -> None:
    out = running_shop(
        "fill",
        "record",
        "NCI/A4471",
        "--by",
        "jt7",
        "--to",
        "2015",
        "--on",
        "2024-06-20",
        "--anyway",
    ).output
    assert "recorded over a refusal" in out


def test_an_overfill_shows_in_the_log(tested: Invoke) -> None:
    tested("fill", "record", "NCI/A4471", "--by", "jt7", "--to", "2600", "--on", "2024-06-20")
    out = tested("fill", "log", "--from", "2024-06-01", "--to", "2024-06-30").output
    assert "overfilled" in out
    only = tested("fill", "log", "--from", "2024-06-01", "--to", "2024-06-30", "--overfills").output
    assert "NCI/A4471" in only


def test_the_log_for_one_cylinder(tested: Invoke) -> None:
    tested("fill", "record", "NCI/A4471", "--by", "jt7", "--to", "2015", "--on", "2024-06-20")
    out = tested("fill", "log", "NCI/A4471").output
    assert "2024-06-20" in out
    assert "within" in out


def test_an_empty_log(tested: Invoke) -> None:
    assert "nothing in the fill log" in tested("fill", "log").output
