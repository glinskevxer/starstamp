"""Every command in the tree, asked for its help and run where it is safe to.

A command that cannot print its own help is broken in a way no other test
catches: the option wiring is evaluated at import time, so a duplicate option
name or a missing callback shows up here and nowhere else. The read only
commands are then run for real against a demo book, because a report that
raises on the shop's own data is the other failure this catches.
"""

from __future__ import annotations

import click
import pytest
from click.testing import CliRunner

from starstamp.cli.main import cli

from .conftest import Invoke


def walk(command: click.Command, path: list[str]) -> list[tuple[list[str], click.Command]]:
    if isinstance(command, click.Group):
        context = click.Context(command)
        found: list[tuple[list[str], click.Command]] = []
        for name in sorted(command.list_commands(context)):
            child = command.get_command(context, name)
            if child is not None:
                found.extend(walk(child, [*path, name]))
        return found
    return [(path, command)]


COMMANDS = walk(cli, [])
READ_ONLY = {
    ("about",),
    ("codes",),
    ("stats",),
    ("check",),
    ("doctor",),
    ("account", "list"),
    ("cylinder", "list"),
    ("cylinder", "find"),
    ("cylinder", "age"),
    ("cylinder", "template"),
    ("tech", "list"),
    ("lot", "open"),
    ("lot", "storage"),
    ("lot", "uncollected"),
    ("notice", "list"),
    ("notice", "late"),
    ("price", "list"),
    ("contract", "accounts"),
    ("invoice", "outstanding"),
    ("invoice", "aging"),
    ("scrap", "outstanding"),
    ("book", "week"),
    ("book", "missed"),
    ("setting", "list"),
    ("requal", "sheet"),
    ("report", "bench"),
    ("report", "worklist"),
    ("report", "unbilled"),
    ("report", "forecast"),
    ("report", "gas"),
    ("report", "cycle"),
    ("report", "day"),
    ("report", "close"),
    ("report", "rig"),
    ("report", "technicians"),
    ("report", "throughput"),
    ("report", "condemnations"),
    ("report", "ownership"),
    ("export", "cylinders"),
    ("verify"),
}


def test_the_tree_is_not_empty() -> None:
    assert len(COMMANDS) >= 60


@pytest.mark.parametrize("path", [path for path, _ in COMMANDS], ids=lambda item: " ".join(item))
def test_every_command_prints_its_help(path: list[str]) -> None:
    result = CliRunner().invoke(cli, [*path, "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output


@pytest.mark.parametrize("path", [path for path, _ in COMMANDS], ids=lambda item: " ".join(item))
def test_every_command_has_a_description(path: list[str]) -> None:
    by_path = {tuple(item): value for item, value in COMMANDS}
    command = by_path[tuple(path)]
    assert (command.help or "").strip(), path


@pytest.mark.parametrize(
    "path",
    [path for path, _ in COMMANDS if tuple(path) in READ_ONLY],
    ids=lambda item: " ".join(item),
)
def test_the_read_only_commands_run_against_a_demo_book(path: list[str], run: Invoke) -> None:
    run("--today", "2025-06-08", "demo", "--cylinders", "8")
    result = run("--today", "2025-06-08", *path, expect=None)
    assert result.exit_code in {0, 7, 8}, result.output


def test_the_money_reports_are_on_the_same_group() -> None:
    """Splitting the module must not move the commands."""
    names = {" ".join(path) for path, _ in COMMANDS}
    for name in (
        "report close",
        "report forecast",
        "report unbilled",
        "report account",
        "report cycle",
    ):
        assert name in names


def test_the_work_reports_are_still_there() -> None:
    names = {" ".join(path) for path, _ in COMMANDS}
    for name in ("report throughput", "report bench", "report pack", "report day"):
        assert name in names
