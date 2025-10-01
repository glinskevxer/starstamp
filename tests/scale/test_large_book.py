"""A book the size of a real shop's, and what the queries do to it.

A requalification shop with five hundred cylinders on its books is a small
shop, and it will have twenty years of records against them. These tests build
a book that shape and then ask SQLite what it intends to do about the queries
the day runs on: a scan of the records of test is fine once and fatal forty
times an hour, and the difference does not show up on the ten row book every
other test uses.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest

from starstamp.model.cylinder import CylinderKey
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.method import Method
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book, open_book
from starstamp.store.events import EventRepository
from starstamp.store.migrations import migrate
from starstamp.store.owners import OwnerRepository

from ..support.factories import make_cylinder, make_owner, make_readings

CYLINDERS = 500
TESTS_EACH = 3


@pytest.fixture(scope="module")
def big_book(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Book]:
    path: Path = tmp_path_factory.mktemp("scale") / "shop.sqlite3"
    with open_book(path) as handle:
        migrate(handle.connection)
        _fill(handle)
        yield handle


def _fill(handle: Book) -> None:
    """Put the fleet and its history in, one cylinder at a time."""
    owners = OwnerRepository(handle.connection)
    owners.add(make_owner())
    owner_id = owners.id_of("WELD1")
    cylinders = CylinderRepository(handle.connection)
    events = EventRepository(handle.connection)
    for index in range(CYLINDERS):
        key = CylinderKey("NCI", f"A{index:05d}")
        cylinders.add(make_cylinder(key=key), owner_id, date(2004, 1, 2))
        cylinder_id = cylinders.id_of(key)
        for pass_number in range(TESTS_EACH):
            events.add(
                RequalificationEvent(
                    cylinder=key,
                    performed_on=date(2010, 1, 4) + timedelta(days=1826 * pass_number),
                    method=Method.VOLUMETRIC,
                    facility_rin="A419",
                    technician_badge="JT7",
                    outcome=Outcome.PASS,
                    system_code="WJ-1",
                    readings=make_readings(),
                    starred=True,
                ),
                cylinder_id,
            )


def plan(book: Book, sql: str, parameters: tuple[object, ...]) -> str:
    rows = book.connection.execute(f"EXPLAIN QUERY PLAN {sql}", parameters).fetchall()
    return " ".join(str(row["detail"]) for row in rows)


def test_the_book_is_the_size_we_meant(big_book: Book) -> None:
    assert CylinderRepository(big_book.connection).count() == CYLINDERS
    assert EventRepository(big_book.connection).count() == CYLINDERS * TESTS_EACH


def test_finding_one_cylinder_uses_its_index(big_book: Book) -> None:
    detail = plan(
        big_book,
        "SELECT * FROM cylinder WHERE manufacturer_symbol = ? AND serial = ?",
        ("NCI", "A00250"),
    )
    assert "SCAN" not in detail
    assert "cylinder" in detail


def test_a_cylinders_history_uses_its_index(big_book: Book) -> None:
    detail = plan(
        big_book,
        "SELECT * FROM requalification WHERE cylinder_id = ? ORDER BY performed_on",
        (12,),
    )
    assert "requalification_by_cylinder" in detail


def test_a_day_of_records_uses_its_index(big_book: Book) -> None:
    detail = plan(big_book, "SELECT * FROM requalification WHERE performed_on = ?", ("2010-01-04",))
    assert "requalification_by_day" in detail


def test_reading_a_history_is_quick(big_book: Book) -> None:
    events = EventRepository(big_book.connection)
    key = CylinderKey("NCI", "A00250")
    started = time.perf_counter()
    for _ in range(20):
        history = events.for_cylinder(key)
    elapsed = time.perf_counter() - started
    assert len(history) == TESTS_EACH
    assert elapsed < 2.0


def test_the_latest_pass_does_not_read_the_whole_book(big_book: Book) -> None:
    events = EventRepository(big_book.connection)
    started = time.perf_counter()
    latest = events.latest_pass(CylinderKey("NCI", "A00499"))
    elapsed = time.perf_counter() - started
    assert latest is not None
    assert elapsed < 0.5


def test_a_window_across_the_whole_book(big_book: Book) -> None:
    events = EventRepository(big_book.connection)
    found = events.between(date(2010, 1, 1), date(2010, 12, 31))
    assert len(found) == CYLINDERS
