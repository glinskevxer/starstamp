from pathlib import Path

import pytest

from starstamp.tools.generate_cli_reference import render, run


def test_the_reference_covers_every_command() -> None:
    text = render()
    assert "### `starstamp requal run`" in text
    assert "### `starstamp cylinder register`" in text
    assert "### `starstamp doctor`" in text
    assert "commands._" in text


def test_options_and_arguments_are_listed() -> None:
    text = render()
    assert "`--tech`" in text
    assert "`KEY` (argument)" in text


def test_the_exit_statuses_are_in_it() -> None:
    text = render()
    assert "- `6` the cylinder may not be filled" in text


def test_the_checked_in_copy_is_current(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["--check"]) == 0
    assert "is current" in capsys.readouterr().out


def test_writing_it_somewhere_else(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "docs" / "cli.md"
    assert run([str(target)]) == 0
    assert target.exists()
    assert "Command reference" in target.read_text()
    assert "wrote" in capsys.readouterr().out


def test_a_stale_copy_fails_the_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "cli.md"
    target.write_text("something else\n")
    assert run([str(target), "--check"]) == 1
    assert "out of date" in capsys.readouterr().err


def test_a_missing_copy_fails_the_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run([str(tmp_path / "nope.md"), "--check"]) == 1
    assert "is not there" in capsys.readouterr().err


def test_writing_it_twice_gives_the_same_file(tmp_path: Path) -> None:
    target = tmp_path / "cli.md"
    run([str(target)])
    first = target.read_text()
    run([str(target)])
    assert target.read_text() == first
