"""Nothing leaves a database connection to the garbage collector.

Python 3.13 raises an unraisable ResourceWarning for a connection that is
collected without being closed, and this suite turns warnings into errors, so
a leak shows up as a failure in whichever test happened to trigger the
collection. That is a miserable way to find one: the test that fails is never
the test that leaked.

This finds them directly. It counts the connections opened and closed while a
piece of work runs, which means it fails in the place the leak actually is.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from starstamp.service.demo import seed
from starstamp.store import maintenance
from starstamp.store.db import Database, open_book
from starstamp.store.migrations import migrate

TODAY = date(2025, 6, 8)


@contextmanager
def counted(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[sqlite3.Connection]]:
    """Watch every connection sqlite3 hands out while the block runs."""
    opened: list[sqlite3.Connection] = []
    real = sqlite3.connect

    def spy(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        connection: sqlite3.Connection = real(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", spy)
    try:
        yield opened
    finally:
        monkeypatch.setattr(sqlite3, "connect", real)


def still_open(connections: list[sqlite3.Connection]) -> list[sqlite3.Connection]:
    left: list[sqlite3.Connection] = []
    for connection in connections:
        try:
            connection.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            continue
        left.append(connection)
    return left


def run_and_count(monkeypatch: pytest.MonkeyPatch, work: Callable[[], None]) -> tuple[int, int]:
    with counted(monkeypatch) as opened:
        work()
        remaining = still_open(opened)
    for connection in remaining:
        connection.close()
    return len(opened), len(remaining)


def test_a_session_closes_what_it_opened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = Database(tmp_path / "shop.sqlite3")

    def work() -> None:
        with database.session() as connection:
            migrate(connection)

    opened, leaked = run_and_count(monkeypatch, work)
    assert opened == 1
    assert leaked == 0


def test_a_book_closes_when_the_block_ends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def work() -> None:
        with open_book(tmp_path / "shop.sqlite3") as handle:
            migrate(handle.connection)

    opened, leaked = run_and_count(monkeypatch, work)
    assert opened == 1
    assert leaked == 0


def test_a_failed_open_leaves_nothing_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    junk = tmp_path / "not-a-book.sqlite3"
    junk.write_text("a packing slip\n")

    def work() -> None:
        with pytest.raises(Exception, match="not a usable book"):
            Database(junk).connect()

    opened, leaked = run_and_count(monkeypatch, work)
    assert opened == 1
    assert leaked == 0


def test_a_backup_closes_both_ends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def work() -> None:
        with open_book(tmp_path / "shop.sqlite3") as handle:
            migrate(handle.connection)
            maintenance.backup(handle, tmp_path / "copy.sqlite3")

    opened, leaked = run_and_count(monkeypatch, work)
    assert opened == 2
    assert leaked == 0


def test_a_restore_closes_everything_it_touched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with open_book(tmp_path / "shop.sqlite3") as handle:
        migrate(handle.connection)
        maintenance.backup(handle, tmp_path / "copy.sqlite3")

    def work() -> None:
        maintenance.restore(tmp_path / "copy.sqlite3", tmp_path / "restored.sqlite3")

    opened, leaked = run_and_count(monkeypatch, work)
    assert opened >= 2
    assert leaked == 0


def test_seeding_a_demo_leaves_one_connection_and_it_is_the_callers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def work() -> None:
        with open_book(tmp_path / "demo.sqlite3") as handle:
            migrate(handle.connection)
            seed(handle, TODAY, cylinders=6)

    opened, leaked = run_and_count(monkeypatch, work)
    assert opened == 1
    assert leaked == 0


def test_the_guard_would_notice_a_leak(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The positive control: a deliberate leak has to be found."""

    def work() -> None:
        sqlite3.connect(tmp_path / "leaked.sqlite3")

    opened, leaked = run_and_count(monkeypatch, work)
    assert opened == 1
    assert leaked == 1
