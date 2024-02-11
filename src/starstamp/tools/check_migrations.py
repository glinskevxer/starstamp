"""Apply every migration to a scratch book and report what happened.

CI runs this before the tests. A migration that only fails on a book which
already has rows is not what this catches; what it catches is the cheap half,
which is the half that has actually broken twice: a file numbered out of
order, a statement the splitter mangles, and a schema that no longer matches
what the repositories select from.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from starstamp.errors import StarstampError
from starstamp.store.db import Database
from starstamp.store.migrations import discover, migrate, schema_version, split_statements


def run(argv: list[str] | None = None) -> int:
    directory = Path(argv[0]) if argv else None
    migrations = discover(directory) if directory else discover()
    statements = sum(len(split_statements(m.sql)) for m in migrations)

    with tempfile.TemporaryDirectory() as work:
        database = Database(Path(work) / "scratch.sqlite3")
        with database.session() as connection:
            applied = migrate(connection, directory) if directory else migrate(connection)
            version = schema_version(connection)
            tables = sorted(
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name NOT LIKE 'sqlite_%' AND name <> 'schema_migration'"
                )
            )
            again = migrate(connection, directory) if directory else migrate(connection)

    problems: list[str] = []
    if len(applied) != len(migrations):
        problems.append(f"{len(migrations)} files but {len(applied)} applied")
    if version != len(migrations):
        problems.append(f"schema version {version} after {len(migrations)} files")
    if again:
        problems.append(f"re-running applied {again} a second time")
    if not tables:
        problems.append("the migrations built no tables at all")

    print(f"{len(migrations)} files, {statements} statements, {len(applied)} applied clean")
    print(f"schema version {version}, {len(tables)} tables")
    for problem in problems:
        print(f"problem: {problem}", file=sys.stderr)
    return 1 if problems else 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except StarstampError as exc:
        print(f"migration check failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
