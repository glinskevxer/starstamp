"""Looking after the file the whole shop depends on.

One SQLite file holds every record of test the shop has, and it lives on a
laptop that gets carried between the bench and the office. So the backup is
not an afterthought: it uses SQLite's own backup interface rather than copying
the file, because copying a database that is being written produces something
that opens cleanly and is missing rows.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from starstamp.errors import ConflictError, StarstampError
from starstamp.store.db import Book, Database
from starstamp.store.migrations import discover, schema_version


@dataclass(frozen=True)
class BackupResult:
    """Where the copy went and how big it is."""

    path: Path
    bytes_written: int
    pages: int

    def describe(self) -> str:
        return f"{self.path} written, {self.bytes_written} bytes over {self.pages} pages"


@dataclass(frozen=True)
class VerifyResult:
    """What the file itself says about its own health."""

    integrity: str
    foreign_keys_broken: int
    schema: int
    expected_schema: int
    freelist_pages: int

    @property
    def is_sound(self) -> bool:
        return (
            self.integrity == "ok"
            and self.foreign_keys_broken == 0
            and self.schema == self.expected_schema
        )

    def describe(self) -> str:
        lines = [f"integrity {self.integrity}", f"schema {self.schema} of {self.expected_schema}"]
        if self.foreign_keys_broken:
            lines.append(f"{self.foreign_keys_broken} rows point at something that is not there")
        if self.freelist_pages:
            lines.append(f"{self.freelist_pages} free pages, worth a vacuum")
        return ", ".join(lines)


def backup(book: Book, target: Path, *, overwrite: bool = False) -> BackupResult:
    """Copy a live book safely, using SQLite's own backup."""
    if target.exists() and not overwrite:
        raise ConflictError(f"{target} is already there; pass overwrite to replace it")
    target.parent.mkdir(parents=True, exist_ok=True)
    pages = 0

    def count(_status: int, _remaining: int, total: int) -> None:
        nonlocal pages
        pages = total

    destination = sqlite3.connect(target)
    try:
        # A `with` on a connection commits; it does not close. On 3.13 the
        # connection that is then left to the collector raises an unraisable
        # ResourceWarning, and on any version it holds the file open on
        # Windows until the collector gets to it.
        book.connection.backup(destination, progress=count)
    finally:
        destination.close()
    return BackupResult(target, target.stat().st_size, pages)


def timestamped_name(book_path: Path, moment: datetime) -> Path:
    """The name a backup gets when nobody says where to put it."""
    stamp = moment.strftime("%Y%m%d-%H%M%S")
    return book_path.with_name(f"{book_path.stem}-{stamp}{book_path.suffix or '.sqlite3'}")


def verify(book: Book) -> VerifyResult:
    """Ask the file about itself, and the code about the file."""
    connection = book.connection
    integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    broken = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    freelist = int(connection.execute("PRAGMA freelist_count").fetchone()[0])
    return VerifyResult(
        integrity=integrity,
        foreign_keys_broken=broken,
        schema=schema_version(connection),
        expected_schema=len(discover()),
        freelist_pages=freelist,
    )


def vacuum(book: Book) -> int:
    """Rebuild the file, returning how many bytes it gave back.

    The write ahead log is checkpointed first. Without that the pages a delete
    freed are still sitting in the -wal file, the main file has not shrunk
    yet, and a vacuum looks as though it did nothing.
    """
    path = book.database.path
    book.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = path.stat().st_size if path.exists() else 0
    book.connection.execute("VACUUM")
    book.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    after = path.stat().st_size if path.exists() else 0
    return max(before - after, 0)


def restore(source: Path, target: Path, *, overwrite: bool = False) -> BackupResult:
    """Put a backup back, checking it is a book before overwriting anything."""
    if not source.exists():
        raise StarstampError(f"there is no backup at {source}")
    if target.exists() and not overwrite:
        raise ConflictError(f"{target} is already there; pass overwrite to replace it")
    database = Database(source)
    with database.session() as connection:
        version = schema_version(connection)
        if version == 0:
            raise StarstampError(f"{source} has no schema, so it is not a book")
    handle = Book(database)
    with handle:
        return backup(handle, target, overwrite=overwrite)
