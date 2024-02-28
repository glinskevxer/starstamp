"""What every command needs: a path to the book and a way to open it.

Commands do not hold a connection between invocations. The shop runs this from
a batch file forty times an hour and leaving a write lock open across an
invocation is how the bench laptop ends up blocking the office.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import click

from starstamp.errors import NotFoundError
from starstamp.model.dates import parse_day
from starstamp.store.db import Book, open_book
from starstamp.store.migrations import migrate, schema_version


@dataclass
class ShopContext:
    """The command line's own state."""

    book_path: Path
    today: date

    @contextmanager
    def open(self, *, create: bool = False) -> Iterator[Book]:
        if not create and not self.book_path.exists():
            raise NotFoundError(f"no book at {self.book_path}; run starstamp init first")
        handle = open_book(self.book_path)
        with handle:
            if not create and schema_version(handle.connection) == 0:
                raise NotFoundError(f"{self.book_path} has no schema; run starstamp init first")
            yield handle

    @contextmanager
    def open_for_write(self, *, create: bool = False) -> Iterator[Book]:
        with self.open(create=create) as handle, handle.write():
            yield handle

    def initialise(self) -> list[str]:
        self.book_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open_book(self.book_path)
        with handle:
            return migrate(handle.connection)


pass_shop = click.make_pass_decorator(ShopContext)


def resolve_day(text: str | None, shop: ShopContext) -> date:
    """A day given on the command line, or today if it was left out."""
    if text is None:
        return shop.today
    return parse_day(text)
