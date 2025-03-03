from datetime import date

import pytest

from starstamp.errors import ConflictError, ValidationError
from starstamp.model.settings import CAPACITY_PER_RIG, CHECK_TOLERANCE
from starstamp.store.db import Book
from starstamp.store.settings import SettingRepository


def test_a_setting_round_trips(book: Book) -> None:
    repository = SettingRepository(book.connection)
    repository.set(CAPACITY_PER_RIG, "40", date(2024, 1, 1), set_by="JT7")
    assert repository.integer(CAPACITY_PER_RIG, date(2024, 6, 1)) == 40


def test_an_unset_setting_reads_its_default(book: Book) -> None:
    assert SettingRepository(book.connection).integer(CAPACITY_PER_RIG, date(2024, 6, 1)) == 24


def test_setting_it_twice_from_the_same_day(book: Book) -> None:
    repository = SettingRepository(book.connection)
    repository.set(CAPACITY_PER_RIG, "40", date(2024, 1, 1))
    with pytest.raises(ConflictError, match="already set from"):
        repository.set(CAPACITY_PER_RIG, "50", date(2024, 1, 1))


def test_the_history_keeps_every_value(book: Book) -> None:
    repository = SettingRepository(book.connection)
    repository.set(CAPACITY_PER_RIG, "30", date(2023, 1, 1))
    repository.set(CAPACITY_PER_RIG, "40", date(2024, 1, 1))
    history = repository.history(CAPACITY_PER_RIG)
    assert [item.value for item in history] == ["30", "40"]
    assert repository.integer(CAPACITY_PER_RIG, date(2023, 6, 1)) == 30


def test_a_bad_value_never_reaches_the_book(book: Book) -> None:
    repository = SettingRepository(book.connection)
    with pytest.raises(ValidationError):
        repository.set(CAPACITY_PER_RIG, "nine hundred", date(2024, 1, 1))
    assert repository.history(CAPACITY_PER_RIG) == []


def test_a_fraction_survives_the_round_trip(book: Book) -> None:
    repository = SettingRepository(book.connection)
    repository.set(CHECK_TOLERANCE, "3/2", date(2024, 1, 1))
    assert repository.settings().fraction(CHECK_TOLERANCE, date(2024, 6, 1)) * 2 == 3
