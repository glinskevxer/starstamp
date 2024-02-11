from pathlib import Path

import pytest

from starstamp.tools.check_migrations import main, run


def test_the_shipped_migrations_check_clean(capsys: pytest.CaptureFixture[str]) -> None:
    assert run([]) == 0
    out = capsys.readouterr().out
    assert "applied clean" in out
    assert "schema version" in out


def test_a_directory_with_no_tables_is_a_problem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "0001_empty.sql").write_text("-- nothing here yet\n")
    assert run([str(tmp_path)]) == 1
    assert "built no tables" in capsys.readouterr().err


def test_a_broken_numbering_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "0002_only.sql").write_text("CREATE TABLE a (x TEXT);\n")
    import sys

    argv = sys.argv
    sys.argv = ["check_migrations", str(tmp_path)]
    try:
        assert main() == 2
    finally:
        sys.argv = argv
    assert "migration check failed" in capsys.readouterr().err


def test_a_scratch_directory_applies(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "0001_core.sql").write_text("CREATE TABLE a (x TEXT);\n")
    (tmp_path / "0002_more.sql").write_text("CREATE TABLE b (y TEXT);\nCREATE INDEX i ON b (y);\n")
    assert run([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "2 files, 3 statements, 2 applied clean" in out
    assert "2 tables" in out
