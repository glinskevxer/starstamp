"""Schema migrations, applied in order and never edited afterwards.

An auditor reads a book that was written over years by whatever version of
this program was installed at the time. So a migration that has been applied
is frozen: its checksum is recorded, and the runner refuses to open a book
whose history no longer matches the files on disk.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from starstamp.errors import ConflictError
from starstamp.store.db import transaction

SQL_DIR = Path(__file__).parent / "sql"
_NAME = re.compile(r"^(?P<number>\d{4})_(?P<slug>[a-z0-9_]+)\.sql$")

CREATE_LEDGER = """
CREATE TABLE IF NOT EXISTS schema_migration (
    number      INTEGER PRIMARY KEY,
    slug        TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


@dataclass(frozen=True)
class Migration:
    number: int
    slug: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text()

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode()).hexdigest()

    @property
    def name(self) -> str:
        return f"{self.number:04d}_{self.slug}"


def discover(directory: Path = SQL_DIR) -> list[Migration]:
    """Every migration file, in number order, with the numbering checked."""
    found: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = _NAME.match(path.name)
        if match is None:
            raise ConflictError(f"migration file is misnamed: {path.name}")
        found.append(Migration(int(match.group("number")), match.group("slug"), path))
    numbers = [migration.number for migration in found]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ConflictError(f"migration numbers are not a run from 1: {numbers}")
    return found


def split_statements(sql: str) -> list[str]:
    """Split a migration into statements without leaning on executescript.

    sqlite3's executescript commits whatever transaction is open before it runs
    a single line, which quietly turns a half applied migration into a
    permanent one. So the runner executes statement by statement, and this is
    the splitter: quotes, both comment styles, and trigger bodies whose inner
    semicolons do not end anything.
    """
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    comment: str | None = None
    in_trigger_body = False
    index = 0
    while index < len(sql):
        char = sql[index]
        pair = sql[index : index + 2]
        if comment == "line":
            if char == "\n":
                comment = None
            current.append(char)
            index += 1
            continue
        if comment == "block":
            current.append(char)
            if pair == "*/":
                current.append("/")
                index += 1
                comment = None
            index += 1
            continue
        if quote is not None:
            current.append(char)
            if char == quote:
                quote = None
            index += 1
            continue
        if pair == "--":
            comment = "line"
            current.append(pair)
            index += 2
            continue
        if pair == "/*":
            comment = "block"
            current.append(pair)
            index += 2
            continue
        if char in "'\"":
            quote = char
            current.append(char)
            index += 1
            continue
        upper = sql[index:].upper()
        if not in_trigger_body and upper.startswith("BEGIN") and _is_trigger("".join(current)):
            in_trigger_body = True
        if in_trigger_body and upper.startswith("END") and _ends_word(sql, index + 3):
            in_trigger_body = False
            current.append(sql[index : index + 3])
            index += 3
            continue
        if char == ";" and not in_trigger_body:
            text = "".join(current).strip()
            if text:
                statements.append(text)
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _is_trigger(text: str) -> bool:
    words = text.upper().split()
    return len(words) >= 2 and words[0] == "CREATE" and "TRIGGER" in words[:4]


def _ends_word(sql: str, index: int) -> bool:
    return index >= len(sql) or not (sql[index].isalnum() or sql[index] == "_")


def statement_count(directory: Path = SQL_DIR) -> int:
    return sum(len(split_statements(migration.sql)) for migration in discover(directory))


def applied(connection: sqlite3.Connection) -> dict[int, str]:
    """The migrations this book already carries, number to checksum."""
    connection.execute(CREATE_LEDGER)
    rows = connection.execute("SELECT number, checksum FROM schema_migration").fetchall()
    return {int(row["number"]): str(row["checksum"]) for row in rows}


def pending(connection: sqlite3.Connection, directory: Path = SQL_DIR) -> list[Migration]:
    """What is left to apply, after checking nothing already applied has moved."""
    known = applied(connection)
    todo: list[Migration] = []
    for migration in discover(directory):
        recorded = known.get(migration.number)
        if recorded is None:
            todo.append(migration)
        elif recorded != migration.checksum:
            raise ConflictError(
                f"migration {migration.name} has changed since it was applied to this book"
            )
    return todo


def migrate(connection: sqlite3.Connection, directory: Path = SQL_DIR) -> list[str]:
    """Apply everything outstanding. Each migration is its own transaction."""
    names: list[str] = []
    for migration in pending(connection, directory):
        with transaction(connection):
            for statement in split_statements(migration.sql):
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migration (number, slug, checksum) VALUES (?, ?, ?)",
                (migration.number, migration.slug, migration.checksum),
            )
        names.append(migration.name)
    return names


def schema_version(connection: sqlite3.Connection) -> int:
    known = applied(connection)
    return max(known) if known else 0
