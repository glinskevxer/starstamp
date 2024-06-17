"""Commands the filling plant and the front counter use."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.model.cylinder import CylinderKey
from starstamp.model.service import lookup_service
from starstamp.service.fill import FillService
from starstamp.text.table import dash, render_table


@click.group()
def fill() -> None:
    """Filling decisions and what is coming due."""


@fill.command("check")
@click.argument("key")
@click.option("--gas", default=None, help="the gas going in, if it is not what it holds now")
@click.option("--on", "day", default=None, help="the day of the fill")
@pass_shop
def check(shop: ShopContext, key: str, gas: str | None, day: str | None) -> None:
    """Say whether a cylinder may be filled, and to what."""
    wanted = CylinderKey.parse(key)
    when = resolve_day(day, shop)
    with shop.open() as handle:
        service = FillService(handle)
        cylinder = service.cylinders.by_key(wanted)
        chosen = lookup_service(gas) if gas else cylinder.service
        decision = service.decision(wanted, chosen, when)
    click.echo(decision.describe())
    if decision.due is not None:
        click.echo(f"  due {decision.due}")
    if not decision.allowed:
        raise SystemExit(6)


@fill.command("due")
@click.option("--within", default=3, show_default=True, help="months ahead to look")
@click.option("--owner", default=None, help="only this account's cylinders")
@click.option("--on", "day", default=None, help="the day to count from")
@pass_shop
def due(shop: ShopContext, within: int, owner: str | None, day: str | None) -> None:
    """List cylinders falling due, soonest first."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        rows = FillService(handle).due_within(
            when, within, owner_code=None if owner is None else owner.upper()
        )
    if not rows:
        click.echo("nothing due")
        return
    click.echo(
        render_table(
            ["cylinder", "owner", "service", "due", "months", "last test"],
            [
                [
                    str(row.cylinder.key),
                    row.cylinder.owner_code,
                    row.cylinder.service.code,
                    dash(row.due),
                    "-" if row.months_left is None else str(row.months_left),
                    dash(None if row.last_pass is None else row.last_pass.performed_on),
                ]
                for row in rows
            ],
            right=(4,),
        )
    )
