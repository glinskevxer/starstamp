from pathlib import Path

import pytest

from starstamp.store.db import Database
from starstamp.store.migrations import migrate
from starstamp.tools.check_indexes import (
    main,
    missing_indexes,
    run,
    tables,
    tables_without_a_primary_key,
)


def test_the_shipped_schema_indexes_every_reference(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run([]) == 0
    out = capsys.readouterr().out
    assert "tables" in out
    assert "indexes" in out


def test_a_reference_with_no_index_is_found(tmp_path: Path) -> None:
    directory = tmp_path / "sql"
    directory.mkdir()
    (directory / "0001_core.sql").write_text(
        "CREATE TABLE parent (id INTEGER PRIMARY KEY);\n"
        "CREATE TABLE child (id INTEGER PRIMARY KEY,"
        " parent_id INTEGER NOT NULL REFERENCES parent(id));\n"
    )
    database = Database(tmp_path / "scratch.sqlite3")
    with database.session() as connection:
        migrate(connection, directory)
        gaps = missing_indexes(connection)
        assert len(gaps) == 1
        assert "child.parent_id points at parent" in str(gaps[0])


def test_an_indexed_reference_is_fine(tmp_path: Path) -> None:
    directory = tmp_path / "sql"
    directory.mkdir()
    (directory / "0001_core.sql").write_text(
        "CREATE TABLE parent (id INTEGER PRIMARY KEY);\n"
        "CREATE TABLE child (id INTEGER PRIMARY KEY,"
        " parent_id INTEGER NOT NULL REFERENCES parent(id));\n"
        "CREATE INDEX child_by_parent ON child (parent_id);\n"
    )
    database = Database(tmp_path / "scratch.sqlite3")
    with database.session() as connection:
        migrate(connection, directory)
        assert missing_indexes(connection) == []


def test_a_composite_index_counts_only_for_its_first_column(tmp_path: Path) -> None:
    directory = tmp_path / "sql"
    directory.mkdir()
    (directory / "0001_core.sql").write_text(
        "CREATE TABLE parent (id INTEGER PRIMARY KEY);\n"
        "CREATE TABLE child (id INTEGER PRIMARY KEY, day TEXT NOT NULL,"
        " parent_id INTEGER NOT NULL REFERENCES parent(id));\n"
        "CREATE INDEX child_by_day ON child (day, parent_id);\n"
    )
    database = Database(tmp_path / "scratch.sqlite3")
    with database.session() as connection:
        migrate(connection, directory)
        assert len(missing_indexes(connection)) == 1


def test_a_table_with_no_primary_key(tmp_path: Path) -> None:
    directory = tmp_path / "sql"
    directory.mkdir()
    (directory / "0001_core.sql").write_text("CREATE TABLE loose (a TEXT, b TEXT);\n")
    database = Database(tmp_path / "scratch.sqlite3")
    with database.session() as connection:
        migrate(connection, directory)
        assert tables_without_a_primary_key(connection) == ["loose"]
        assert tables(connection) == ["loose"]


def test_the_command_reports_problems(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    directory = tmp_path / "sql"
    directory.mkdir()
    (directory / "0001_core.sql").write_text("CREATE TABLE loose (a TEXT);\n")
    assert run([str(directory)]) == 1
    assert "no primary key" in capsys.readouterr().err


def test_a_broken_directory_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    directory = tmp_path / "sql"
    directory.mkdir()
    (directory / "0002_only.sql").write_text("CREATE TABLE a (id INTEGER PRIMARY KEY);\n")
    import sys

    argv = sys.argv
    sys.argv = ["check_indexes", str(directory)]
    try:
        assert main() == 2
    finally:
        sys.argv = argv
    assert "index check failed" in capsys.readouterr().err
