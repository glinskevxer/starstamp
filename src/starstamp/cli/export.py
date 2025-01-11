"""Export commands.

Everything writes to standard output by default, because that is what a shop
piping into a file or an email actually wants. The --out option exists for
Windows, where redirecting a console script mangles the line endings.
"""

from __future__ import annotations

from pathlib import Path

import click

from starstamp.cli.context import ShopContext, pass_shop
from starstamp.cli.windows import resolve as resolve_window
from starstamp.reporting import export


def _emit(text: str, out: Path | None) -> None:
    if out is None:
        click.echo(text, nl=False)
        return
    out.write_text(text, newline="\n")
    lines = max(text.count("\n") - 1, 0)
    click.echo(f"wrote {lines} rows to {out}")


@click.group("export")
def export_group() -> None:
    """Comma separated output."""


@export_group.command("cylinders")
@click.option("--owner", default=None, help="only this account's cylinders")
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@pass_shop
def cylinders(shop: ShopContext, owner: str | None, out: Path | None) -> None:
    """Every cylinder on the books."""
    with shop.open() as handle:
        text = export.cylinders_csv(handle, owner)
    _emit(text, out)


@export_group.command("records")
@click.option("--from", "first", default=None, help="first day, YYYY-MM-DD")
@click.option("--to", "last", default=None, help="last day, YYYY-MM-DD")
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@pass_shop
def records(shop: ShopContext, first: str | None, last: str | None, out: Path | None) -> None:
    """Records of test in a window."""
    window = resolve_window(shop.today, first=first, last=last)
    start, end = window.first, window.last
    with shop.open() as handle:
        text = export.events_csv(handle, start, end)
    _emit(text, out)


@export_group.command("invoices")
@click.argument("owner")
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@pass_shop
def invoices(shop: ShopContext, owner: str, out: Path | None) -> None:
    """Every invoice line for an account."""
    with shop.open() as handle:
        text = export.invoices_csv(handle, owner)
    _emit(text, out)
