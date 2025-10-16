from pathlib import Path

import pytest

from starstamp.tools.check_repo import (
    Complaint,
    declarations,
    generated_files,
    leftover_markers,
    missing_docstrings,
    modules,
    packages_without_tests,
    run,
    undeclared_generated_files,
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


def test_the_generators_are_found_by_looking_not_by_naming() -> None:
    """The rule reads the generators, so a third one is covered by arriving."""
    assert sorted(generated_files()) == ["docs/cli.md", "docs/domain.md"]


def test_every_generated_file_is_declared_as_generated() -> None:
    assert undeclared_generated_files() == []


def test_the_declarations_are_read_off_the_file_that_ships() -> None:
    declared = declarations()
    assert declared["docs/cli.md"] == "linguist-generated=true"
    assert declared["docs/domain.md"] == "linguist-generated=true"


def test_an_undeclared_generated_file_is_found(tmp_path: Path) -> None:
    """The positive control. Take the declaration away and the rule complains."""
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "generate_thing.py").write_text('"""A generator."""\n\nTARGET = "docs/thing.md"\n')
    attributes = tmp_path / ".gitattributes"
    attributes.write_text("docs/other.md linguist-generated=true\n")
    found = undeclared_generated_files(tools, attributes)
    assert len(found) == 1
    assert "docs/thing.md" in str(found[0])


def test_a_missing_attributes_file_means_nothing_is_declared(tmp_path: Path) -> None:
    assert declarations(tmp_path / "absent") == {}


def test_comments_and_blank_lines_are_not_declarations(tmp_path: Path) -> None:
    attributes = tmp_path / ".gitattributes"
    attributes.write_text("# a comment\n\ndocs/cli.md linguist-generated=true\n")
    assert declarations(attributes) == {"docs/cli.md": "linguist-generated=true"}
