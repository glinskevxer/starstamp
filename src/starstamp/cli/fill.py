"""Commands the filling plant and the front counter use."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.cli.requal import parse_pounds
from starstamp.cli.windows import resolve as resolve_window
from starstamp.model.cylinder import CylinderKey
from starstamp.model.service import lookup_service
from starstamp.model.units import Pressure
from starstamp.service.fill import FillService
from starstamp.service.filling import FillingService
from starstamp.text import machine
from starstamp.text.table import dash, render_table


@click.group()
def fill() -> None:
    """Filling decisions and what is coming due."""


@fill.command("check")
@click.argument("key")
@click.option("--gas", default=None, help="the gas going in, if it is not what it holds now")
@click.option("--on", "day", default=None, help="the day of the fill")
@click.option("--json", "as_json", is_flag=True, help="print it for a script instead")
@pass_shop
def check(shop: ShopContext, key: str, gas: str | None, day: str | None, as_json: bool) -> None:
    """Say whether a cylinder may be filled, and to what."""
    wanted = CylinderKey.parse(key)
    when = resolve_day(day, shop)
    with shop.open() as handle:
        service = FillService(handle)
        cylinder = service.cylinders.by_key(wanted)
        chosen = lookup_service(gas) if gas else cylinder.service
        decision = service.decision(wanted, chosen, when)
    if as_json:
        click.echo(machine.dumps(machine.fill_decision(decision)))
    else:
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


@fill.command("record")
@click.argument("key")
@click.option("--gas", default=None, help="the gas going in, if not what it holds")
@click.option("--by", "filler", required=True, help="the badge of whoever filled it")
@click.option("--to", "pressure", default=None, help="the pressure reached, psig")
@click.option("--weight", default=None, help="the weight put in, pounds, for a liquefied gas")
@click.option("--at", "temperature", default=70, show_default=True, help="degrees F at the fill")
@click.option("--on", "day", default=None)
@click.option("--note", default=None)
@click.option("--anyway", is_flag=True, help="record a fill the shop would have refused")
@pass_shop
def record(
    shop: ShopContext,
    key: str,
    gas: str | None,
    filler: str,
    pressure: str | None,
    weight: str | None,
    temperature: int,
    day: str | None,
    note: str | None,
    anyway: bool,
) -> None:
    """Record a fill, refusing the ones the shop should not do."""
    wanted = CylinderKey.parse(key)
    when = resolve_day(day, shop)
    with shop.open_for_write() as handle:
        service = FillingService(handle)
        cylinder = service.cylinders.by_key(wanted)
        chosen = lookup_service(gas) if gas else cylinder.service
        outcome = service.record(
            wanted,
            chosen,
            when,
            filler,
            pressure=None if pressure is None else Pressure.parse(pressure),
            weight_hundredths_lb=None if weight is None else parse_pounds(weight),
            temperature_f=temperature,
            note=note,
            override=anyway,
        )
    click.echo(outcome.describe())


@fill.command("log")
@click.argument("key", required=False)
@click.option("--from", "first", default=None, help="first day of the window")
@click.option("--to", "last", default=None, help="last day of the window")
@click.option("--overfills", "only_overfills", is_flag=True, help="only the overfills")
@pass_shop
def log(
    shop: ShopContext,
    key: str | None,
    first: str | None,
    last: str | None,
    only_overfills: bool,
) -> None:
    """What has been put into cylinders."""
    window = resolve_window(shop.today, first=first, last=last)
    with shop.open() as handle:
        service = FillingService(handle)
        if key is not None:
            found = service.history(CylinderKey.parse(key))
        elif only_overfills:
            found = service.overfills(window.first, window.last)
        else:
            found = service.fills.between(window.first, window.last)
        verdicts = {
            item.fill_id: service.fills.verdict_of(item.fill_id)
            for item in found
            if item.fill_id is not None
        }
    if not found:
        click.echo("nothing in the fill log")
        return
    click.echo(
        render_table(
            ["date", "cylinder", "gas", "reading", "at", "verdict", "by"],
            [
                [
                    item.filled_on.isoformat(),
                    item.cylinder_key,
                    item.service.code,
                    f"{(item.weight_hundredths_lb or 0) / 100:.2f} lb"
                    if item.is_by_weight
                    else str(item.pressure),
                    f"{item.temperature_f}F",
                    verdicts[item.fill_id].value if item.fill_id in verdicts else "-",
                    item.filler_badge,
                ]
                for item in found
            ],
        )
    )
