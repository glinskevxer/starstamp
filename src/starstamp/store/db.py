"""The connection to the shop's book.

One SQLite file holds everything. It gets carried on a laptop between the
bench and the office, it gets copied onto a stick for the auditor, and it is
opened by two processes more often than anyone admits. So foreign keys are on,
the journal is write ahead, and a busy database waits instead of erroring.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType

from starstamp.errors import ConflictError, StarstampError

PRAGMAS = (
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA busy_timeout = 5000",
)


class Database:
    """A handle on one book file. Cheap to make, holds no connection."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        """Open a configured connection, or leave nothing open if it fails.

        A pragma that fails on a file which is not a database used to leave the
        connection object behind, and the caller only ever saw the exception.
        """
        connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            for pragma in PRAGMAS:
                connection.execute(pragma)
        except sqlite3.DatabaseError as exc:
            connection.close()
            raise StarstampError(f"{self.path} is not a usable book: {exc}") from exc
        return connection

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def exists(self) -> bool:
        return self.path.exists()


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a unit of work, rolling back anything that raises.

    Autocommit is off at the sqlite3 level because isolation_level is None, so
    the transaction is spelled out here rather than left to the driver.
    """
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    connection.execute("COMMIT")


class Book:
    """A database plus an open connection, used as a context manager."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self._connection: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise ConflictError("the book is not open")
        return self._connection

    def __enter__(self) -> Book:
        self._connection = self.database.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        with transaction(self.connection) as connection:
            yield connection


def open_book(path: Path) -> Book:
    return Book(Database(path))
