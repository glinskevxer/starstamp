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


def test_a_dry_run_writes_nothing(tested: Invoke) -> None:
    out = tested(
        "restate",
        "certificate",
        "WJ-1",
        "burette",
        "EB-19",
        "2024-06-01",
        "--reason",
        "restated",
        "--dry-run",
    ).output
    assert "1 records would be reversed" in out
    assert "recorded" in tested("requal", "history", "NCI/A4471", "--all").output


def test_a_restatement_pulls_the_record(tested: Invoke) -> None:
    out = tested(
        "restate",
        "certificate",
        "WJ-1",
        "burette",
        "EB-19",
        "2024-06-01",
        "--reason",
        "the house restated the scale",
    ).output
    assert "1 records between" in out
    assert "is no longer requalified" in out
    history = tested("requal", "history", "NCI/A4471", "--all").output
    assert "reversed" in history
    assert "replacement" in history


def test_the_cylinder_stops_being_fillable(tested: Invoke) -> None:
    tested(
        "restate",
        "certificate",
        "WJ-1",
        "burette",
        "EB-19",
        "2024-06-01",
        "--reason",
        "restated",
    )
    result = tested("--today", "2024-07-01", "fill", "check", "NCI/A4471", expect=6)
    assert "no standing requalification" in result.output


def test_reversing_one_record(tested: Invoke) -> None:
    out = tested("restate", "reverse", "1", "--reason", "wrong cylinder on the sheet").output
    assert "reversed 1" in out
    tested("restate", "reverse", "1", "--reason", "again", expect=4)


def test_the_window_listing(tested: Invoke) -> None:
    out = tested("restate", "window", "WJ-1", "2024-06-01", "2024-06-30").output
    assert "NCI/A4471" in out
    assert (
        "nothing in that window"
        in tested("restate", "window", "WJ-1", "2023-01-01", "2023-12-31").output
    )


def test_a_certificate_that_is_not_on_file(tested: Invoke) -> None:
    tested(
        "restate",
        "certificate",
        "WJ-1",
        "burette",
        "NOPE-1",
        "2024-06-01",
        "--reason",
        "restated",
        expect=3,
    )


def test_correcting_a_record(tested: Invoke) -> None:
    out = tested(
        "restate",
        "correct",
        "1",
        "--reason",
        "typed from the wrong line",
        "--applied",
        "3358",
        "--total",
        "112.0",
        "--permanent",
        "2.0",
    ).output
    assert "reversed and rewritten" in out
    assert "total 110.0 cc to 112.0 cc" in out
    history = tested("requal", "history", "NCI/A4471", "--all").output
    assert "reversed" in history
    assert "replacement" in history


def test_a_correction_that_changes_nothing(tested: Invoke) -> None:
    tested("restate", "correct", "1", "--reason", "none", "--tech", "jt7", expect=4)
