"""Shared plumbing for the repositories.

The repositories are hand written rather than generated. There are not many of
them, the queries are the interesting part of most of them, and an auditor who
asks how a number was arrived at deserves an answer that fits on a screen.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import date
from typing import Any

from starstamp.errors import NotFoundError
from starstamp.model.dates import parse_day


class Repository:
    """A table's worth of queries, holding the connection and nothing else."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def _one(self, sql: str, parameters: Iterable[Any], missing: str) -> sqlite3.Row:
        row: sqlite3.Row | None = self.connection.execute(sql, tuple(parameters)).fetchone()
        if row is None:
            raise NotFoundError(missing)
        return row

    def _all(self, sql: str, parameters: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return list(self.connection.execute(sql, tuple(parameters)).fetchall())

    def _count(self, sql: str, parameters: Iterable[Any] = ()) -> int:
        row = self.connection.execute(sql, tuple(parameters)).fetchone()
        return int(row[0])


def as_day(value: object) -> date:
    if isinstance(value, str):
        return parse_day(value)
    raise TypeError(f"expected a stored date string, got {value!r}")


def as_optional_day(value: object) -> date | None:
    if value is None:
        return None
    return as_day(value)


def day_text(day: date) -> str:
    return day.isoformat()


def optional_day_text(day: date | None) -> str | None:
    return None if day is None else day.isoformat()


def as_int(value: object) -> int:
    if isinstance(value, int):
        return value
    raise TypeError(f"expected a stored integer, got {value!r}")


def as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    return as_int(value)


def as_text(value: object) -> str:
    if isinstance(value, str):
        return value
    raise TypeError(f"expected stored text, got {value!r}")


def as_optional_text(value: object) -> str | None:
    if value is None:
        return None
    return as_text(value)
