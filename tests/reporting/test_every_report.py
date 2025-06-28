"""Every report, against an empty book and against the demo book.

Reports are the part of this package that gets written once and read a year
later, and the failure they have is not a wrong number: it is an exception on
a book where nothing has happened yet, or on one where something unusual has.
So each one is run twice here, and all that is asserted is that it produced
text rather than a traceback.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from starstamp.model.cylinder import CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.reporting import (
    aging,
    audit,
    close,
    condemnation,
    cycle,
    daybook,
    export,
    fleet,
    forecast,
    gases,
    life,
    pack,
    rig,
    statement,
    technician,
    throughput,
    unbilled,
)
from starstamp.service.demo import seed
from starstamp.store.db import Book, open_book
from starstamp.store.migrations import migrate

TODAY = date(2025, 6, 8)
FIRST = date(2025, 5, 1)
LAST = date(2025, 6, 30)
KEY = CylinderKey("NCI", "D0000")


@pytest.fixture
def empty(tmp_path: Path) -> Book:
    handle = open_book(tmp_path / "empty.sqlite3")
    handle.__enter__()
    migrate(handle.connection)
    return handle


@pytest.fixture
def busy(tmp_path: Path) -> Book:
    handle = open_book(tmp_path / "busy.sqlite3")
    handle.__enter__()
    migrate(handle.connection)
    seed(handle, TODAY, cylinders=12)
    return handle


def every_report(book: Book) -> list[str]:
    """Run every report the package has and collect what it printed."""
    return [
        throughput.render(
            throughput.by_month(throughput.standing_between(book, FIRST, LAST)), "month"
        ),
        throughput.render_summary(throughput.standing_between(book, FIRST, LAST)),
        condemnation.render(condemnation.build(book, FIRST, LAST)),
        rig.render(rig.build_all(book, FIRST, LAST), TODAY),
        fleet.render(fleet.build(book, "WELD1", TODAY)) if _has_account(book) else "",
        forecast.render(forecast.build(book, TODAY, 24)),
        aging.render(aging.build(book, TODAY)),
        gases.render(gases.build(book, FIRST, LAST)),
        cycle.render(cycle.build(book, FIRST, LAST)),
        daybook.render(daybook.build(book, TODAY)),
        unbilled.render(unbilled.build(book, TODAY)),
        technician.render(technician.build(book, FIRST, LAST)),
        close.render(close.build(book, StampedMonth(2025, 6), TODAY)),
        export.cylinders_csv(book),
        export.events_csv(book, FIRST, LAST),
    ]


def _has_account(book: Book) -> bool:
    from starstamp.store.owners import OwnerRepository

    return bool(OwnerRepository(book.connection).all())


def test_every_report_survives_an_empty_book(empty: Book) -> None:
    for text in every_report(empty):
        assert isinstance(text, str)


def test_every_report_says_something_about_a_busy_book(busy: Book) -> None:
    printed = every_report(busy)
    assert all(isinstance(text, str) for text in printed)
    assert any("WELD1" in text for text in printed)


def test_the_statement_and_the_packet_on_a_busy_book(busy: Book) -> None:
    text = statement.render(statement.build(busy, "WELD1", FIRST, LAST, TODAY))
    assert "WELD1" in text
    packet = audit.render(audit.build(busy, KEY), today=TODAY)
    assert "NCI/D0000" in packet


def test_a_life_reads_on_a_busy_book(busy: Book) -> None:
    text = life.render(life.build(busy, KEY), TODAY)
    assert "NCI/D0000" in text


def test_an_audit_pack_writes_from_a_busy_book(busy: Book, tmp_path: Path) -> None:
    result = pack.write(busy, tmp_path / "pack", FIRST, LAST, TODAY)
    assert result.cylinders > 0
    assert (tmp_path / "pack" / "index.txt").exists()


def test_an_audit_pack_from_an_empty_book(empty: Book, tmp_path: Path) -> None:
    result = pack.write(empty, tmp_path / "pack", FIRST, LAST, TODAY)
    assert result.cylinders == 0
    assert result.is_complete
