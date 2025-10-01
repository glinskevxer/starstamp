"""The demo book, which is the first thing anybody new runs."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from starstamp.model.cylinder import CylinderStatus
from starstamp.service.demo import seed
from starstamp.service.doctor import Doctor
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book, open_book
from starstamp.store.events import EventRepository
from starstamp.store.migrations import migrate
from starstamp.store.notices import NoticeRepository

TODAY = date(2025, 6, 8)


@pytest.fixture
def demo(tmp_path: Path) -> Iterator[Book]:
    """A demo book that is closed again when the test is done.

    The book has to stay open across the whole test, and a fixture that opens
    one and never closes it leaves the connection to the collector. Python
    3.13 turns that into an unraisable ResourceWarning, which this suite reads
    as an error, so every fixture here yields.
    """
    with open_book(tmp_path / "demo.sqlite3") as handle:
        migrate(handle.connection)
        seed(handle, TODAY)
        yield handle


def test_the_demo_has_a_fleet(demo: Book) -> None:
    assert CylinderRepository(demo.connection).count() == 40


def test_it_has_work_in_it(demo: Book) -> None:
    events = EventRepository(demo.connection)
    assert events.count() >= 20
    assert any(event.is_condemnation for event in events.between(date(2025, 1, 1), TODAY))


def test_it_condemns_some_and_passes_most(demo: Book) -> None:
    cylinders = CylinderRepository(demo.connection)
    condemned = len(cylinders.with_status(CylinderStatus.CONDEMNED))
    assert 1 <= condemned <= 6
    assert len(cylinders.with_status(CylinderStatus.IN_SERVICE)) > 20


def test_the_condemnations_have_letters_waiting(demo: Book) -> None:
    assert NoticeRepository(demo.connection).unsent()


def test_the_demo_book_is_sound(demo: Book) -> None:
    report = Doctor(demo).run(TODAY)
    assert report.is_clean, report.describe()


def test_the_cylinders_are_a_mixture(demo: Book) -> None:
    cylinders = CylinderRepository(demo.connection)
    fleet = cylinders.search()
    specs = {str(item.specification) for item in fleet}
    services = {item.service.code for item in fleet}
    assert len(specs) >= 3
    assert len(services) >= 4


def test_every_cylinder_has_a_valve_that_suits_its_gas(demo: Book) -> None:
    from starstamp.rules.valve import matches

    for cylinder in CylinderRepository(demo.connection).search():
        assert matches(cylinder, cylinder.service), str(cylinder.key)


def test_seeding_a_smaller_shop(tmp_path: Path) -> None:
    with open_book(tmp_path / "small.sqlite3") as handle:
        migrate(handle.connection)
        result = seed(handle, TODAY, cylinders=8)
        assert result.cylinders == 8
        assert "seeded 8 cylinders" in result.describe()
