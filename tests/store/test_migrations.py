from pathlib import Path

import pytest

from starstamp.errors import ConflictError
from starstamp.store.db import Database
from starstamp.store.migrations import (
    discover,
    migrate,
    pending,
    schema_version,
)


def test_the_shipped_migrations_are_numbered_from_one() -> None:
    found = discover()
    assert found
    assert [m.number for m in found] == list(range(1, len(found) + 1))


def test_migrate_applies_everything_once(tmp_path: Path) -> None:
    database = Database(tmp_path / "shop.sqlite3")
    with database.session() as connection:
        first = migrate(connection)
        assert "0001_core" in first
        assert migrate(connection) == []
        assert schema_version(connection) == len(first)


def test_migrate_builds_the_core_tables(tmp_path: Path) -> None:
    database = Database(tmp_path / "shop.sqlite3")
    with database.session() as connection:
        migrate(connection)
        names = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"owner_account", "cylinder", "schema_migration"} <= names


def test_a_changed_migration_is_refused(tmp_path: Path) -> None:
    directory = tmp_path / "sql"
    directory.mkdir()
    (directory / "0001_core.sql").write_text("CREATE TABLE a (x TEXT);")
    database = Database(tmp_path / "shop.sqlite3")
    with database.session() as connection:
        migrate(connection, directory)
        (directory / "0001_core.sql").write_text("CREATE TABLE a (x TEXT, y TEXT);")
        with pytest.raises(ConflictError, match="has changed"):
            pending(connection, directory)


def test_a_gap_in_the_numbering_is_refused(tmp_path: Path) -> None:
    directory = tmp_path / "sql"
    directory.mkdir()
    (directory / "0001_core.sql").write_text("CREATE TABLE a (x TEXT);")
    (directory / "0003_later.sql").write_text("CREATE TABLE b (x TEXT);")
    with pytest.raises(ConflictError, match="not a run from 1"):
        discover(directory)


def test_a_misnamed_file_is_refused(tmp_path: Path) -> None:
    directory = tmp_path / "sql"
    directory.mkdir()
    (directory / "core.sql").write_text("CREATE TABLE a (x TEXT);")
    with pytest.raises(ConflictError, match="misnamed"):
        discover(directory)


def test_a_failing_migration_leaves_the_book_alone(tmp_path: Path) -> None:
    directory = tmp_path / "sql"
    directory.mkdir()
    (directory / "0001_core.sql").write_text("CREATE TABLE a (x TEXT);")
    (directory / "0002_broken.sql").write_text("CREATE TABLE b (x TEXT); SELECT nope();")
    database = Database(tmp_path / "shop.sqlite3")
    with database.session() as connection:
        with pytest.raises(Exception, match="nope"):
            migrate(connection, directory)
        assert schema_version(connection) == 1
        remaining = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "b" not in remaining


def test_schema_version_of_an_empty_book(tmp_path: Path) -> None:
    database = Database(tmp_path / "shop.sqlite3")
    with database.session() as connection:
        assert schema_version(connection) == 0
