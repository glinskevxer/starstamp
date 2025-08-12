from pathlib import Path

import pytest

from starstamp.tools.check_repo import (
    Complaint,
    leftover_markers,
    missing_docstrings,
    modules,
    packages_without_tests,
    run,
)


def test_this_repository_keeps_its_own_rules(capsys: pytest.CaptureFixture[str]) -> None:
    assert run([]) == 0
    assert "modules checked" in capsys.readouterr().out


def test_every_shipped_module_says_what_it_is_for() -> None:
    assert missing_docstrings() == []


def test_nothing_was_left_behind() -> None:
    assert leftover_markers() == []


def test_every_source_package_has_tests_beside_it() -> None:
    assert packages_without_tests() == []


def test_a_module_with_no_docstring_is_found(tmp_path: Path) -> None:
    (tmp_path / "bare.py").write_text("x = 1\n")
    found = missing_docstrings(tmp_path)
    assert len(found) == 1
    assert "no module docstring" in str(found[0])


def test_an_empty_init_is_allowed(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text("")
    assert missing_docstrings(tmp_path) == []


def test_a_marker_left_behind_is_found(tmp_path: Path) -> None:
    # The marker is built rather than written out, because this checker reads
    # the test suite too and a literal here would flag this file.
    marker = "# " + "TO" + "DO: come back to this"
    (tmp_path / "left.py").write_text(f'"""A module."""\n\n{marker}\n')
    found = leftover_markers((tmp_path,))
    assert len(found) == 1
    assert "come back to this" in str(found[0])


def test_a_package_with_no_tests_is_found(tmp_path: Path) -> None:
    source = tmp_path / "src"
    (source / "widgets").mkdir(parents=True)
    (source / "widgets" / "__init__.py").write_text('"""Widgets."""\n')
    tests = tmp_path / "tests"
    tests.mkdir()
    found = packages_without_tests(source, tests)
    assert len(found) == 1
    assert "no tests/widgets beside it" in str(found[0])


def test_modules_skips_the_caches(tmp_path: Path) -> None:
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "a.py").write_text("")
    (tmp_path / "b.py").write_text('"""B."""\n')
    assert [path.name for path in modules(tmp_path)] == ["b.py"]


def test_a_complaint_reads_as_a_line() -> None:
    complaint = Complaint("docstring", "src/x.py", "no module docstring")
    assert str(complaint) == "docstring: src/x.py: no module docstring"
