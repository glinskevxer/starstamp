"""Commands for dealing with condemned cylinders."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.model.cylinder import CylinderKey
from starstamp.model.disposal import DisposalMethod
from starstamp.service.disposal import DisposalService
from starstamp.store.disposals import DisposalRepository
from starstamp.text.table import dash, render_table


@click.group()
def scrap() -> None:
    """Condemned cylinders and what became of them."""


@scrap.command("render")
@click.argument("key")
@click.argument("method")
@click.option("--tech", required=True, help="who did it")
@click.option("--witness", default=None, help="who watched")
@click.option("--ticket", default=None, help="the scrap yard's ticket number")
@click.option("--return-to-owner", is_flag=True, help="the owner asked for it back")
@click.option("--note", default=None)
@click.option("--on", "day", default=None)
@pass_shop
def render(
    shop: ShopContext,
    key: str,
    method: str,
    tech: str,
    witness: str | None,
    ticket: str | None,
    return_to_owner: bool,
    note: str | None,
    day: str | None,
) -> None:
    """Render a condemned cylinder incapable of holding pressure."""
    wanted = CylinderKey.parse(key)
    with shop.open_for_write() as handle:
        disposal = DisposalService(handle).dispose(
            wanted,
            DisposalMethod.parse(method),
            resolve_day(day, shop),
            tech,
            witness_badge=witness,
            scrap_ticket=ticket,
            returned_to_owner=return_to_owner,
            note=note,
        )
    click.echo(disposal.summary())


@scrap.command("outstanding")
@click.option("--on", "day", default=None)
@click.option("--late-only", is_flag=True, help="only the ones past the deadline")
@pass_shop
def outstanding(shop: ShopContext, day: str | None, late_only: bool) -> None:
    """Condemned cylinders nobody has dealt with."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        service = DisposalService(handle)
        rows = service.late(when) if late_only else service.outstanding(when)
    if not rows:
        click.echo("nothing waiting")
        return
    for row in rows:
        click.echo(row.describe())


@scrap.command("log")
@click.option("--from", "first", required=True, help="first day of the window")
@click.option("--to", "last", required=True, help="last day of the window")
@pass_shop
def log(shop: ShopContext, first: str, last: str) -> None:
    """Everything dealt with in a window."""
    from starstamp.model.dates import parse_day

    with shop.open() as handle:
        found = DisposalRepository(handle.connection).between(parse_day(first), parse_day(last))
    if not found:
        click.echo("nothing in that window")
        return
    click.echo(
        render_table(
            ["date", "cylinder", "method", "tech", "witness", "ticket", "days"],
            [
                [
                    item.performed_on.isoformat(),
                    item.cylinder_key,
                    item.method.label,
                    item.technician_badge,
                    dash(item.witness_badge),
                    dash(item.scrap_ticket),
                    str(item.days_taken),
                ]
                for item in found
            ],
            right=(6,),
        )
    )
