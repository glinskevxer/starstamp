from pathlib import Path

import pytest

from starstamp.tools.generate_domain_reference import MODEL, RULES, render, run, sections


def test_every_rule_module_is_in_the_reference() -> None:
    text = render()
    for section in sections(RULES):
        assert f"## {section.name}" in text


def test_the_vocabulary_is_there_too() -> None:
    text = render()
    assert "# The vocabulary" in text
    assert any(section.name.startswith("model/") for section in sections(MODEL))


def test_the_summary_is_the_first_line_of_the_docstring() -> None:
    found = {section.name: section for section in sections(RULES)}
    fill = found["rules/fill.py"]
    assert fill.summary.startswith("Whether a cylinder may be filled today")
    assert "condemned" in fill.body


def test_the_checked_in_copy_is_current(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["--check"]) == 0
    assert "is current" in capsys.readouterr().out


def test_writing_it_somewhere_else(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "domain.md"
    assert run([str(target)]) == 0
    assert "What decides what" in target.read_text()
    assert "modules" in capsys.readouterr().out


def test_a_stale_copy_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "domain.md"
    target.write_text("something else\n")
    assert run([str(target), "--check"]) == 1
    assert "out of date" in capsys.readouterr().err


def test_a_missing_copy_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run([str(tmp_path / "nope.md"), "--check"]) == 1
    assert "is not there" in capsys.readouterr().err


def test_a_module_with_no_docstring_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "bare.py").write_text("x = 1\n")
    assert sections(tmp_path) == []


def test_writing_it_twice_gives_the_same_file(tmp_path: Path) -> None:
    target = tmp_path / "domain.md"
    run([str(target)])
    first = target.read_text()
    run([str(target)])
    assert target.read_text() == first
