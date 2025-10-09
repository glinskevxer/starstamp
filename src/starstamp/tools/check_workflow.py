"""Check every starstamp command line in the build against the real CLI.

It reads the workflow files and the scripts they call, because the chain the
build runs lives in scripts/smoke.sh and a checker that only read the workflow
would have nothing left to check.

This exists because of a class of mistake nothing else here catches. Every
test in the suite calls the command line with its arguments already in the
right shape, so a workflow step that puts a group option after the subcommand
passes every test and fails in CI five minutes later.

The checker walks the click tree for each command line it finds in the
workflow files and names the token that is wrong. It deliberately does not run
anything: a command line can be wrong in ways that only a shop's book would
show, and this is about the shape.
"""

from __future__ import annotations

import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

import click

from starstamp.cli.main import cli

WORKFLOWS = Path(".github/workflows")
SCRIPTS = Path("scripts")
DEFAULT_ROOTS = (WORKFLOWS, SCRIPTS)
_INVOCATION = re.compile(r"(?<![\w/-])starstamp\s")
_PLACEHOLDER = re.compile(r"\$\{\{.*?\}\}|\$[A-Za-z_{(]")


@dataclass(frozen=True)
class Problem:
    """One command line that will not run."""

    source: str
    line: int
    command: str
    detail: str

    def __str__(self) -> str:
        return f"{self.source}:{self.line}: {self.detail}\n    {self.command}"


def join_continuations(text: str) -> list[tuple[int, str]]:
    """Fold shell line continuations, keeping the first line's number."""
    out: list[tuple[int, str]] = []
    buffer = ""
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not buffer:
            start = number
        if line.endswith("\\"):
            buffer += line[:-1].strip() + " "
            continue
        out.append((start, (buffer + line.strip()).strip()))
        buffer = ""
    if buffer:
        out.append((start, buffer.strip()))
    return out


def command_lines(text: str) -> list[tuple[int, str]]:
    """Every starstamp invocation in a file, with its line number."""
    found: list[tuple[int, str]] = []
    for number, line in join_continuations(text):
        match = _INVOCATION.search(line)
        if match is None:
            continue
        found.append((number, line[match.start() :]))
    return found


def _options(command: click.Command) -> set[str]:
    names: set[str] = set()
    for parameter in command.params:
        names.update(parameter.opts)
        names.update(parameter.secondary_opts)
    return names


def check_line(source: str, number: int, line: str) -> list[Problem]:
    """Walk one command line through the click tree."""
    if _PLACEHOLDER.search(line):
        return []
    try:
        tokens = shlex.split(line)
    except ValueError as exc:
        return [Problem(source, number, line, f"cannot be read as a command line: {exc}")]

    problems: list[Problem] = []
    current: click.Command = cli
    path = ["starstamp"]
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("-"):
            name = token.split("=", 1)[0]
            if name not in _options(current):
                problems.append(
                    Problem(source, number, line, f"{' '.join(path)} has no option {name}")
                )
                return problems
            parameter = next(
                item for item in current.params if name in item.opts or name in item.secondary_opts
            )
            takes_value = not isinstance(parameter, click.Option) or not parameter.is_flag
            if takes_value and "=" not in token:
                index += 1
            index += 1
            continue
        if isinstance(current, click.Group):
            child = current.get_command(click.Context(current), token)
            if child is None:
                offered = ", ".join(sorted(current.list_commands(click.Context(current))))
                problems.append(
                    Problem(
                        source,
                        number,
                        line,
                        f"{' '.join(path)} has no command {token}; it has {offered}",
                    )
                )
                return problems
            current = child
            path.append(token)
            index += 1
            continue
        index += 1
    if isinstance(current, click.Group):
        problems.append(Problem(source, number, line, f"{' '.join(path)} needs a subcommand"))
    return problems


def check_path(path: Path) -> list[Problem]:
    text = path.read_text()
    problems: list[Problem] = []
    for number, line in command_lines(text):
        problems.extend(check_line(str(path), number, line))
    return problems


def run(argv: list[str] | None = None) -> int:
    roots = [Path(item) for item in (argv or [])] or list(DEFAULT_ROOTS)
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            for pattern in ("*.yml", "*.yaml", "*.sh"):
                files.extend(sorted(root.glob(pattern)))
        elif root.exists():
            files.append(root)
    if not files:
        print("no build files to check", file=sys.stderr)
        return 0

    problems: list[Problem] = []
    checked = 0
    for path in files:
        lines = command_lines(path.read_text())
        checked += len(lines)
        problems.extend(check_path(path))

    print(f"{len(files)} build files, {checked} starstamp command lines")
    for problem in problems:
        print(str(problem), file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
