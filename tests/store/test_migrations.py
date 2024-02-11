from pathlib import Path

import pytest

from starstamp.errors import ConflictError
from starstamp.store.db import Database
from starstamp.store.migrations import (
    discover,
    migrate,
    pending,
    schema_version,
    split_statements,
    statement_count,
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


def test_split_ignores_semicolons_inside_strings() -> None:
    sql = "INSERT INTO a VALUES ('one; two'); INSERT INTO a VALUES ('three');"
    assert split_statements(sql) == [
        "INSERT INTO a VALUES ('one; two')",
        "INSERT INTO a VALUES ('three')",
    ]


def test_split_keeps_comments_with_their_statement() -> None:
    sql = "-- a note; with a semicolon\nCREATE TABLE a (x TEXT);"
    statements = split_statements(sql)
    assert len(statements) == 1
    assert statements[0].startswith("-- a note")


def test_split_handles_block_comments() -> None:
    sql = "/* one; two */ CREATE TABLE a (x TEXT); CREATE TABLE b (y TEXT);"
    assert len(split_statements(sql)) == 2


def test_split_keeps_a_trigger_body_whole() -> None:
    sql = (
        "CREATE TABLE a (x TEXT);\n"
        "CREATE TRIGGER t AFTER INSERT ON a BEGIN\n"
        "  INSERT INTO a VALUES ('x');\n"
        "  INSERT INTO a VALUES ('y');\n"
        "END;\n"
        "CREATE TABLE b (y TEXT);"
    )
    statements = split_statements(sql)
    assert len(statements) == 3
    assert statements[1].count("INSERT INTO") == 2


def test_split_drops_empty_statements() -> None:
    assert split_statements(";;\n;  ;") == []


def test_split_keeps_a_trailing_statement_without_a_semicolon() -> None:
    assert split_statements("CREATE TABLE a (x TEXT)") == ["CREATE TABLE a (x TEXT)"]


def test_split_handles_a_quoted_identifier() -> None:
    sql = 'CREATE TABLE "odd;name" (x TEXT); CREATE TABLE b (y TEXT);'
    assert len(split_statements(sql)) == 2


def test_statement_count_covers_every_shipped_migration() -> None:
    assert statement_count() >= 4
