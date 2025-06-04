"""Write the command line reference out of the command line itself.

Hand written command documentation is wrong within a month. This walks the
click tree and writes docs/cli.md from it, and CI runs the same walk and fails
if what is checked in differs. So the reference is either right or the build
is red, and there is no third state where it quietly rots.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from starstamp.cli.main import STATUS_MEANINGS, cli

TARGET = Path("docs/cli.md")

HEADER = """# Command reference

Written by `python -m starstamp.tools.generate_cli_reference`. Do not edit it
by hand: the build regenerates it and compares.

Every command takes the group options first:

    starstamp --book shop.sqlite3 [--today YYYY-MM-DD] <command> ...

## Exit statuses

"""


def _options(command: click.Command) -> list[str]:
    lines: list[str] = []
    for parameter in command.params:
        if isinstance(parameter, click.Option):
            names = ", ".join(parameter.opts)
            help_text = parameter.help or ""
            lines.append(f"  - `{names}` {help_text}".rstrip())
        elif isinstance(parameter, click.Argument):
            name = (parameter.name or "argument").upper()
            lines.append(f"  - `{name}` (argument)")
    return lines


def _walk(command: click.Command, path: list[str], lines: list[str]) -> int:
    counted = 0
    if isinstance(command, click.Group):
        context = click.Context(command)
        for name in sorted(command.list_commands(context)):
            child = command.get_command(context, name)
            if child is None:
                continue
            counted += _walk(child, [*path, name], lines)
        return counted

    summary = (command.help or "").strip().splitlines()
    lines.append(f"### `{' '.join(path)}`")
    lines.append("")
    lines.append(summary[0] if summary else "No description.")
    options = _options(command)
    if options:
        lines.append("")
        lines.extend(options)
    lines.append("")
    return counted + 1


def render() -> str:
    lines: list[str] = []
    for status, meaning in STATUS_MEANINGS:
        lines.append(f"- `{status}` {meaning}")
    lines.append("")
    lines.append("## Commands")
    lines.append("")
    count = _walk(cli, ["starstamp"], lines)
    lines.append(f"_{count} commands._")
    return HEADER + "\n".join(lines) + "\n"


def run(argv: list[str] | None = None) -> int:
    """Write the reference, or check the one on disk against it."""
    arguments = argv or []
    check_only = "--check" in arguments
    target = TARGET
    for item in arguments:
        if not item.startswith("--"):
            target = Path(item)

    text = render()
    if check_only:
        if not target.exists():
            print(f"{target} is not there; run the generator", file=sys.stderr)
            return 1
        current = target.read_text()
        if current != text:
            print(f"{target} is out of date; run the generator", file=sys.stderr)
            return 1
        print(f"{target} is current")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, newline="\n")
    print(f"wrote {target}, {text.count(chr(10))} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
