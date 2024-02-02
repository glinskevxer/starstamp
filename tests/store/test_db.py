import sqlite3
from pathlib import Path
from typing import Any

import pytest

from starstamp.errors import ConflictError, StarstampError
from starstamp.store.db import Database, open_book, transaction


def test_connect_turns_foreign_keys_on(tmp_path: Path) -> None:
    database = Database(tmp_path / "shop.sqlite3")
    with database.session() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_connect_uses_write_ahead_logging(tmp_path: Path) -> None:
    database = Database(tmp_path / "shop.sqlite3")
    with database.session() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_rows_come_back_as_mappings(tmp_path: Path) -> None:
    database = Database(tmp_path / "shop.sqlite3")
    with database.session() as connection:
        connection.execute("CREATE TABLE t (a TEXT, b INTEGER)")
        connection.execute("INSERT INTO t VALUES ('x', 3)")
        row = connection.execute("SELECT * FROM t").fetchone()
        assert row["a"] == "x"
        assert row["b"] == 3


def test_a_file_that_is_not_a_database_is_refused(tmp_path: Path) -> None:
    junk = tmp_path / "notes.txt"
    junk.write_text("this is a packing slip, not a book\n")
    with pytest.raises(StarstampError):
        Database(junk).connect()


def test_a_failed_connect_leaves_nothing_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    junk = tmp_path / "notes.txt"
    junk.write_text("still not a book\n")
    opened: list[sqlite3.Connection] = []
    real_connect = sqlite3.connect

    def spy(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        connection: sqlite3.Connection = real_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", spy)
    with pytest.raises(StarstampError):
        Database(junk).connect()

    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0].execute("SELECT 1")


def test_exists(tmp_path: Path) -> None:
    database = Database(tmp_path / "shop.sqlite3")
    assert not database.exists()
    with database.session():
        pass
    assert database.exists()


def test_transaction_rolls_back_on_error(tmp_path: Path) -> None:
    database = Database(tmp_path / "shop.sqlite3")
    with database.session() as connection:
        connection.execute("CREATE TABLE t (a TEXT)")

        def fail() -> None:
            with transaction(connection):
                connection.execute("INSERT INTO t VALUES ('x')")
                raise RuntimeError("bench alarm")

        with pytest.raises(RuntimeError):
            fail()
        assert connection.execute("SELECT count(*) FROM t").fetchone()[0] == 0


def test_transaction_commits(tmp_path: Path) -> None:
    database = Database(tmp_path / "shop.sqlite3")
    with database.session() as connection:
        connection.execute("CREATE TABLE t (a TEXT)")
        with transaction(connection):
            connection.execute("INSERT INTO t VALUES ('x')")
    with database.session() as connection:
        assert connection.execute("SELECT count(*) FROM t").fetchone()[0] == 1


def test_book_refuses_use_before_open(tmp_path: Path) -> None:
    book = open_book(tmp_path / "shop.sqlite3")
    with pytest.raises(ConflictError):
        _ = book.connection


def test_book_writes_and_closes(tmp_path: Path) -> None:
    path = tmp_path / "shop.sqlite3"
    with open_book(path) as book:
        with book.write() as connection:
            connection.execute("CREATE TABLE t (a TEXT)")
            connection.execute("INSERT INTO t VALUES ('x')")
        assert book.connection.execute("SELECT count(*) FROM t").fetchone()[0] == 1
    with open_book(path) as book:
        assert book.connection.execute("SELECT a FROM t").fetchone()["a"] == "x"
