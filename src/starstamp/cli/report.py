"""Reporting commands."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.cli.windows import resolve as resolve_window
from starstamp.model.cylinder import CylinderKey
from starstamp.reporting import audit, condemnation, fleet, rig, technician, throughput
from starstamp.service.receiving import ReceivingService
from starstamp.service.repair import RepairService
from starstamp.text.table import render_table


@click.group()
def report() -> None:
    """Reports the shop hands to somebody else."""


@report.command("packet")
@click.argument("key")
@click.option("--all", "show_all", is_flag=True, help="include reversed records")
@pass_shop
def packet(shop: ShopContext, key: str, show_all: bool) -> None:
    """The audit packet for one cylinder."""
    wanted = CylinderKey.parse(key)
    with shop.open() as handle:
        built = audit.build(handle, wanted, standing_only=not show_all)
    click.echo(audit.render(built, today=shop.today))


@report.command("throughput")
@click.option("--from", "first", default=None, help="first day, YYYY-MM-DD")
@click.option("--to", "last", default=None, help="last day, YYYY-MM-DD")
@click.option(
    "--by",
    "grouping",
    type=click.Choice(["month", "method", "technician"]),
    default="month",
    show_default=True,
)
@pass_shop
def throughput_report(
    shop: ShopContext, first: str | None, last: str | None, grouping: str
) -> None:
    """What the shop got through in a window."""
    window = resolve_window(shop.today, first=first, last=last)
    start, end = window.first, window.last
    with shop.open() as handle:
        events = throughput.standing_between(handle, start, end)
    click.echo(f"{start.isoformat()} to {end.isoformat()}")
    if grouping == "month":
        click.echo(throughput.render(throughput.by_month(events), "month"))
    elif grouping == "method":
        click.echo(throughput.render(throughput.by_method(events), "method"))
    else:
        click.echo(throughput.render(throughput.by_technician(events), "technician"))
    click.echo("")
    click.echo(throughput.render_summary(events))


@report.command("day")
@click.option("--on", "day", default=None, help="the day to read, YYYY-MM-DD")
@pass_shop
def day_report(shop: ShopContext, day: str | None) -> None:
    """Everything that happened on one day."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        events = throughput.standing_between(handle, when, when)
    if not events:
        click.echo(f"nothing on {when.isoformat()}")
        return
    for event in events:
        click.echo(event.summary())
    click.echo("")
    click.echo(throughput.render_summary(events))


@report.command("rig")
@click.argument("system_code", required=False)
@click.option("--from", "first", default=None, help="first day of the window")
@click.option("--to", "last", default=None, help="last day of the window")
@pass_shop
def rig_report(
    shop: ShopContext, system_code: str | None, first: str | None, last: str | None
) -> None:
    """How the test systems are doing."""
    window = resolve_window(shop.today, first=first, last=last)
    start, end = window.first, window.last
    with shop.open() as handle:
        if system_code:
            standings = [rig.build(handle, system_code.upper(), start, end)]
        else:
            standings = rig.build_all(handle, start, end)
    click.echo(f"{start.isoformat()} to {end.isoformat()}")
    click.echo(rig.render(standings, shop.today))


@report.command("fleet")
@click.argument("owner")
@click.option("--within", default=6, show_default=True, help="months ahead to list")
@click.option("--on", "day", default=None, help="the day to read it for")
@pass_shop
def fleet_report(shop: ShopContext, owner: str, within: int, day: str | None) -> None:
    """One account's cylinders, taken together."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        standing = fleet.build(handle, owner, when)
    click.echo(fleet.render(standing, months=within))


@report.command("floor")
@click.argument("owner")
@pass_shop
def floor(shop: ShopContext, owner: str) -> None:
    """What of an account's is in the shop right now."""
    with shop.open() as handle:
        found = fleet.in_shop(handle, owner)
    if not found:
        click.echo(f"nothing of {owner.upper()} is in the shop")
        return
    for cylinder in found:
        click.echo(f"{cylinder.key} {cylinder.specification} {cylinder.status.value}")


@report.command("condemnations")
@click.option("--from", "first", default=None, help="first day of the window")
@click.option("--to", "last", default=None, help="last day of the window")
@pass_shop
def condemnation_report(shop: ShopContext, first: str | None, last: str | None) -> None:
    """What was condemned, and what those cylinders had in common."""
    window = resolve_window(shop.today, first=first, last=last)
    start, end = window.first, window.last
    with shop.open() as handle:
        analysis = condemnation.build(handle, start, end)
    click.echo(condemnation.render(analysis))


@report.command("bench")
@click.option("--on", "day", default=None, help="the day to make the sheet for")
@pass_shop
def bench_sheet(shop: ShopContext, day: str | None) -> None:
    """The work sheet: what is in the shop and what each one needs.

    The counter prints this in the morning. It is deliberately one line per
    cylinder with the reason it is here, because a sheet that needs a second
    lookup gets left on the desk.
    """
    when = resolve_day(day, shop)
    with shop.open() as handle:
        service = ReceivingService(handle)
        repairs = RepairService(handle)
        lines: list[list[str]] = []
        for standing in service.open_standing():
            for line in standing.lines:
                if line.is_settled:
                    continue
                key = CylinderKey.parse(line.cylinder_key)
                cylinder = service.cylinders.by_key(key)
                held = repairs.held_by(key)
                lines.append(
                    [
                        standing.lot.number,
                        str(key),
                        str(cylinder.specification),
                        cylinder.service.code,
                        cylinder.status.value,
                        "-" if held is None else "; ".join(held.reasons),
                    ]
                )
    if not lines:
        click.echo(f"nothing on the bench for {when.isoformat()}")
        return
    click.echo(f"bench sheet {when.isoformat()}")
    click.echo(render_table(["lot", "cylinder", "spec", "gas", "status", "held for"], lines))


@report.command("technicians")
@click.option("--from", "first", default=None, help="first day of the window")
@click.option("--to", "last", default=None, help="last day of the window")
@pass_shop
def technician_report(shop: ShopContext, first: str | None, last: str | None) -> None:
    """What each person got through, and who sits away from the middle."""
    window = resolve_window(shop.today, first=first, last=last)
    start, end = window.first, window.last
    with shop.open() as handle:
        comparison = technician.build(handle, start, end)
    click.echo(f"{start.isoformat()} to {end.isoformat()}")
    click.echo(technician.render(comparison))
    mix = technician.method_mix(comparison)
    if mix:
        click.echo("")
        click.echo(
            render_table(
                ["method", "cylinders"],
                [[label, str(count)] for label, count in mix.items()],
                right=(1,),
            )
        )
