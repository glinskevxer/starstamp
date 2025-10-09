from pathlib import Path

import pytest

from starstamp.tools.check_workflow import check_line, command_lines, join_continuations, run


def test_the_shipped_build_is_clean(capsys: pytest.CaptureFixture[str]) -> None:
    assert run([]) == 0
    out = capsys.readouterr().out
    assert "starstamp command lines" in out
    assert "build files" in out


def test_it_finds_the_command_lines_in_the_smoke_script() -> None:
    text = Path("scripts/smoke.sh").read_text()
    assert len(command_lines(text)) >= 8


def test_it_reads_the_scripts_as_well_as_the_workflows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run(["scripts"]) == 0
    assert "starstamp command lines" in capsys.readouterr().out


def test_continuations_are_folded() -> None:
    folded = join_continuations("run: starstamp --book b.sqlite3 \\\n  account add X Y\nnext: 1")
    assert folded[0][1].endswith("account add X Y")
    assert folded[0][0] == 1
    assert folded[1][0] == 3


def test_a_good_line_passes() -> None:
    assert check_line("x", 1, "starstamp --book shop.sqlite3 about") == []


def test_a_group_option_after_the_subcommand_is_caught() -> None:
    problems = check_line("x", 1, "starstamp about --book shop.sqlite3")
    assert len(problems) == 1
    assert "starstamp about has no option --book" in str(problems[0])


def test_an_unknown_command_lists_what_there_is() -> None:
    problems = check_line("x", 3, "starstamp --book b requal nope NCI/A1")
    assert "has no command nope" in str(problems[0])
    assert "history" in str(problems[0])


def test_an_unknown_option_is_caught() -> None:
    problems = check_line("x", 1, "starstamp --book b cylinder list --wobbly")
    assert "has no option --wobbly" in str(problems[0])


def test_a_group_without_a_subcommand_is_caught() -> None:
    problems = check_line("x", 1, "starstamp --book b cylinder")
    assert "needs a subcommand" in str(problems[0])


def test_a_flag_does_not_eat_the_next_token() -> None:
    assert check_line("x", 1, "starstamp --book b requal history NCI/A1 --all") == []


def test_lines_with_shell_variables_are_left_alone() -> None:
    assert check_line("x", 1, 'starstamp --book "$BOOK" wobbly') == []
    assert check_line("x", 1, "starstamp --book b ${{ matrix.thing }}") == []


def test_an_unreadable_line() -> None:
    problems = check_line("x", 1, "starstamp --book 'unclosed")
    assert "cannot be read" in str(problems[0])


def test_a_bad_workflow_file_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = tmp_path / "bad.yml"
    workflow.write_text("      - run: starstamp about --book shop.sqlite3\n")
    assert run([str(workflow)]) == 1
    assert "has no option --book" in capsys.readouterr().err


def test_nothing_to_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run([str(tmp_path / "missing")]) == 0
    assert "no build files" in capsys.readouterr().err


def test_a_directory_of_workflows(tmp_path: Path) -> None:
    (tmp_path / "one.yml").write_text("run: starstamp --book b about\n")
    (tmp_path / "two.yaml").write_text("run: starstamp --book b cylinder list\n")
    assert run([str(tmp_path)]) == 0
