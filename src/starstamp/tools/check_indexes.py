"""Check the schema indexes every foreign key it declares.

SQLite will happily let a table point at another with nothing to look it up
by, and the shop notices two years later when a cylinder with four hundred
records of test takes a second to open. The rule is narrow and mechanical: a
column that references another table has to be the first column of some index,
and every table has to have a primary key.

The check runs against a scratch book built from the migrations, so it reads
what the schema actually is rather than what the SQL looks like.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from starstamp.errors import StarstampError
from starstamp.store.db import Database
from starstamp.store.migrations import migrate

SKIP = {"schema_migration"}


@dataclass(frozen=True)
class Gap:
    """One reference with nothing to look it up by."""

    table: str
    column: str
    points_at: str

    def __str__(self) -> str:
        return f"{self.table}.{self.column} points at {self.points_at} with no index on it"


def tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        " ORDER BY name"
    ).fetchall()
    return [str(row["name"]) for row in rows if str(row["name"]) not in SKIP]


def leading_indexed_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    """Columns that some index looks up by first, including the primary key."""
    found: set[str] = set()
    for row in connection.execute(f"PRAGMA table_info('{table}')").fetchall():
        if int(row["pk"]):
            found.add(str(row["name"]))
    for index in connection.execute(f"PRAGMA index_list('{table}')").fetchall():
        columns = connection.execute(f"PRAGMA index_info('{index['name']}')").fetchall()
        if columns:
            first = columns[0]["name"]
            if first is not None:
                found.add(str(first))
    return found


def missing_indexes(connection: sqlite3.Connection) -> list[Gap]:
    gaps: list[Gap] = []
    for table in tables(connection):
        indexed = leading_indexed_columns(connection, table)
        for key in connection.execute(f"PRAGMA foreign_key_list('{table}')").fetchall():
            column = str(key["from"])
            if column not in indexed:
                gaps.append(Gap(table, column, str(key["table"])))
    return gaps


def tables_without_a_primary_key(connection: sqlite3.Connection) -> list[str]:
    bare: list[str] = []
    for table in tables(connection):
        columns = connection.execute(f"PRAGMA table_info('{table}')").fetchall()
        if not any(int(row["pk"]) for row in columns):
            bare.append(table)
    return bare


def run(argv: list[str] | None = None) -> int:
    directory = Path(argv[0]) if argv else None
    with tempfile.TemporaryDirectory() as work:
        database = Database(Path(work) / "scratch.sqlite3")
        with database.session() as connection:
            migrate(connection, directory) if directory else migrate(connection)
            gaps = missing_indexes(connection)
            bare = tables_without_a_primary_key(connection)
            counted = len(tables(connection))
            indexes = connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE type = 'index'"
            ).fetchone()[0]

    print(f"{counted} tables, {indexes} indexes")
    for gap in gaps:
        print(f"problem: {gap}", file=sys.stderr)
    for table in bare:
        print(f"problem: {table} has no primary key", file=sys.stderr)
    return 1 if gaps or bare else 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except StarstampError as exc:
        print(f"index check failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
