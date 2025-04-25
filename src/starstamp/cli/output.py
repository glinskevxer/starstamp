"""What every command does with what it found.

Nine commands had the same four lines in them: check for nothing, say so in
their own words, build a table, print it. The words differed, which is the
part that mattered to whoever was reading, so they stay per command; the rest
lives here.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import click

from starstamp.text.table import render_pairs, render_table


def echo_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    right: Sequence[int] = (),
    empty: str = "nothing to show",
) -> bool:
    """Print a table, or the empty line. Says whether it printed anything."""
    if not rows:
        click.echo(empty)
        return False
    click.echo(render_table(headers, rows, right=right))
    return True


def echo_pairs(items: Iterable[tuple[str, str]]) -> None:
    click.echo(render_pairs(items))


def echo_lines(lines: Iterable[str], *, empty: str | None = None) -> bool:
    """Print one line each, or the empty line if there are none."""
    printed = False
    for line in lines:
        click.echo(line)
        printed = True
    if not printed and empty is not None:
        click.echo(empty)
    return printed


def echo_count(count: int, singular: str, plural: str | None = None) -> None:
    word = singular if count == 1 else (plural or f"{singular}s")
    click.echo(f"{count} {word}")
