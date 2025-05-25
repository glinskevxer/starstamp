"""Every status this command line can exit with, and something that causes it.

The shop drives this from batch files that branch on the status, so a status
that means one thing on Tuesday and another on Wednesday is worse than an
error message nobody reads. Each row here pins one status to one cause.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from starstamp.cli.main import STATUS_MEANINGS

from .conftest import DAY, Invoke


def test_the_meanings_are_a_run_from_zero() -> None:
    statuses = [status for status, _ in STATUS_MEANINGS]
    assert statuses == list(range(len(statuses)))


def test_the_codes_command_lists_them(shop: Invoke) -> None:
    out = shop("codes").output
    for status, meaning in STATUS_MEANINGS:
        assert f"{status}  {meaning}" in out


def test_zero_is_a_good_run(shop: Invoke) -> None:
    shop("about")


def test_one_is_something_with_no_name(run: Invoke, book_path: Path) -> None:
    book_path.write_text("this is not a book\n")
    result = run("about", expect=1)
    assert "not a usable book" in result.output


def test_two_is_bad_input(shop: Invoke) -> None:
    shop(
        "cylinder",
        "register",
        "nokey",
        "--owner",
        "X",
        "--spec",
        "DOT-3AA2015",
        "--dom",
        "06-98",
        "--service",
        "N2",
        expect=2,
    )


def test_three_is_something_the_book_does_not_hold(shop: Invoke) -> None:
    shop("account", "show", "nope", expect=3)


def test_four_is_a_state_that_refuses(shop: Invoke) -> None:
    shop("account", "add", "weld1", "Cascade", "--opened", "2019-04-01")
    shop("account", "add", "weld1", "Cascade again", expect=4)


def test_five_is_the_regulations(running_shop: Invoke) -> None:
    running_shop(
        "repair", "do", "NCI/A4471", "weld", "--tech", "jt7", "--on", "2024-06-14", expect=5
    )


def test_six_is_a_cylinder_that_may_not_be_filled(running_shop: Invoke) -> None:
    running_shop("fill", "check", "NCI/A4471", expect=6)


def test_seven_and_eight_are_the_check(running_shop: Invoke) -> None:
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
    running_shop("check", "--on", "2024-06-13", expect=8)
    running_shop("notice", "draft", "--on", "2024-06-13")
    running_shop("check", "--on", "2024-07-20", expect=7)


def test_nine_is_a_file_that_is_not_sound(running_shop: Invoke, book_path: Path) -> None:
    import sqlite3

    connection = sqlite3.connect(book_path)
    connection.execute("DELETE FROM schema_migration WHERE number > 3")
    connection.commit()
    connection.close()
    running_shop("verify", expect=9)


def test_ten_is_the_doctor(running_shop: Invoke, book_path: Path) -> None:
    import sqlite3

    connection = sqlite3.connect(book_path)
    connection.execute("DELETE FROM schema_migration WHERE number > 3")
    connection.commit()
    connection.close()
    running_shop("doctor", expect=10)


@pytest.mark.parametrize("status", [status for status, _ in STATUS_MEANINGS])
def test_every_status_has_a_meaning(status: int) -> None:
    assert dict(STATUS_MEANINGS)[status]
