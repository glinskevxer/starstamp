"""The starstamp command line."""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import click

from starstamp import __version__
from starstamp.cli.accounts import account
from starstamp.cli.billing import invoice, price
from starstamp.cli.check import check, stats
from starstamp.cli.context import ShopContext, pass_shop
from starstamp.cli.cylinders import cylinder
from starstamp.cli.disposal import scrap
from starstamp.cli.export import export_group
from starstamp.cli.fill import fill
from starstamp.cli.lots import lot
from starstamp.cli.notices import notice
from starstamp.cli.repairs import repair
from starstamp.cli.report import report
from starstamp.cli.requal import requal
from starstamp.cli.restate import restate
from starstamp.cli.shopfloor import facility, rig, tech
from starstamp.errors import (
    ConflictError,
    NotFoundError,
    RuleViolationError,
    StarstampError,
    ValidationError,
)

EXIT_CODES: tuple[tuple[type[StarstampError], int], ...] = (
    (ValidationError, 2),
    (NotFoundError, 3),
    (ConflictError, 4),
    (RuleViolationError, 5),
)


def exit_code_for(error: StarstampError) -> int:
    """Map a domain error onto the status the shop's batch files check."""
    for kind, code in EXIT_CODES:
        if isinstance(error, kind):
            return code
    return 1


class ShopError(click.ClickException):
    """A domain error on its way out through click, carrying its own status."""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code

    def format_message(self) -> str:
        return f"error: {self.message}"


class ShopGroup(click.Group):
    """The top level group, which is where domain errors become exit codes.

    Doing this in the entry point instead would mean the tests exercise a
    different path from the one the shop runs, and the exit codes are the part
    the shop's batch files actually depend on.
    """

    def invoke(self, ctx: click.Context) -> object:
        try:
            return super().invoke(ctx)
        except StarstampError as exc:
            raise ShopError(str(exc), exit_code_for(exc)) from exc


@click.group(cls=ShopGroup)
@click.version_option(__version__, prog_name="starstamp")
@click.option(
    "--book",
    "book_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default="shop.sqlite3",
    show_default=True,
    envvar="STARSTAMP_BOOK",
    help="the SQLite file this shop keeps its records in",
)
@click.option(
    "--today",
    "today",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="pretend the day is this one, for backdated paperwork",
)
@click.pass_context
def cli(context: click.Context, book_path: Path, today: datetime | None) -> None:
    """Records for a cylinder requalification shop."""
    context.obj = ShopContext(book_path=book_path, today=(today.date() if today else date.today()))


@cli.command()
@pass_shop
def init(shop: ShopContext) -> None:
    """Create the book, or bring an existing one up to the current schema."""
    applied = shop.initialise()
    if applied:
        for name in applied:
            click.echo(f"applied {name}")
    else:
        click.echo("already current")


@cli.command()
@pass_shop
def about(shop: ShopContext) -> None:
    """Say what book is open and what is in it."""
    from starstamp.store.migrations import schema_version

    click.echo(f"book {shop.book_path}")
    if not shop.book_path.exists():
        click.echo("no book yet")
        return
    with shop.open() as handle:
        click.echo(f"schema version {schema_version(handle.connection)}")
        count = handle.connection.execute("SELECT count(*) FROM cylinder").fetchone()[0]
        click.echo(f"{count} cylinders")


cli.add_command(account)
cli.add_command(cylinder)
cli.add_command(requal)
cli.add_command(facility)
cli.add_command(tech)
cli.add_command(rig)
cli.add_command(fill)
cli.add_command(restate)
cli.add_command(report)
cli.add_command(lot)
cli.add_command(price)
cli.add_command(invoice)
cli.add_command(repair)
cli.add_command(notice)
cli.add_command(export_group)
cli.add_command(check)
cli.add_command(stats)
cli.add_command(scrap)


def run() -> int:
    """The console entry point, which turns domain errors into exit codes."""
    try:
        cli.main(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.Abort:
        click.echo("aborted", err=True)
        return 130
    except StarstampError as exc:
        click.echo(f"error: {exc}", err=True)
        return exit_code_for(exc)
    return 0


if __name__ == "__main__":
    sys.exit(run())
