"""The guards that turn a surprising row into a readable error.

Every repository reads its rows through these, and they exist because a column
that comes back as None where an integer was expected produces a TypeError
three layers up with nothing in it about which column. They are cheap to test
and they are the difference between a five minute fix and an afternoon.
"""

from __future__ import annotations

from datetime import date

import pytest

from starstamp.errors import NotFoundError, ValidationError
from starstamp.store.db import Book
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_day,
    as_optional_int,
    as_optional_text,
    as_text,
    day_text,
    optional_day_text,
)


def test_days_read_and_write() -> None:
    assert as_day("2024-06-12") == date(2024, 6, 12)
    assert day_text(date(2024, 6, 12)) == "2024-06-12"
    assert as_optional_day(None) is None
    assert optional_day_text(None) is None


def test_a_day_that_is_not_a_day() -> None:
    with pytest.raises(TypeError, match="stored date string"):
        as_day(20240612)
    with pytest.raises(ValidationError):
        as_day("the twelfth")


def test_integers_and_text() -> None:
    assert as_int(3) == 3
    assert as_optional_int(None) is None
    assert as_text("x") == "x"
    assert as_optional_text(None) is None


def test_a_column_of_the_wrong_kind_says_which() -> None:
    with pytest.raises(TypeError, match="stored integer"):
        as_int("3")
    with pytest.raises(TypeError, match="stored text"):
        as_text(3)


def test_the_repository_helpers_run_queries(book: Book) -> None:
    repository = Repository(book.connection)
    assert repository._count("SELECT count(*) FROM cylinder") == 0
    assert repository._all("SELECT * FROM cylinder") == []
    with pytest.raises(NotFoundError, match="nothing there"):
        repository._one("SELECT * FROM cylinder WHERE id = ?", (1,), "nothing there")
