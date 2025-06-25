"""Reporting commands."""

from __future__ import annotations

from pathlib import Path

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.cli.output import echo_table
from starstamp.cli.windows import parse_month
from starstamp.cli.windows import resolve as resolve_window
from starstamp.model.cylinder import CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.reporting import (
    audit,
    close,
    condemnation,
    cycle,
    daybook,
    fleet,
    forecast,
    gases,
    pack,
    rig,
    technician,
    throughput,
    unbilled,
)
from starstamp.service.receiving import ReceivingService
from starstamp.service.repair import RepairService
from starstamp.service.worklist import WorklistService
from starstamp.store.transfers import TransferRepository
from starstamp.text import machine
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
@click.option("--tests-only", is_flag=True, help="only the records of test")
@pass_shop
def day_report(shop: ShopContext, day: str | None, tests_only: bool) -> None:
    """Everything that happened on one day."""
    when = resolve_day(day, shop)
    if tests_only:
        with shop.open() as handle:
            events = throughput.standing_between(handle, when, when)
        if not events:
            click.echo(f"nothing on {when.isoformat()}")
            return
        for event in events:
            click.echo(event.summary())
        click.echo("")
        click.echo(throughput.render_summary(events))
        return
    with shop.open() as handle:
        book = daybook.build(handle, when)
    click.echo(daybook.render(book))


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


@report.command("forecast")
@click.option("--months", default=24, show_default=True, help="how far ahead to look")
@click.option("--on", "day", default=None, help="the day to count from")
@click.option("--json", "as_json", is_flag=True, help="print it for a script instead")
@pass_shop
def forecast_report(shop: ShopContext, months: int, day: str | None, as_json: bool) -> None:
    """What is coming, from the due dates already in the book."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        built = forecast.build(handle, when, months)
    if as_json:
        click.echo(machine.dumps(machine.forecast(built)))
        return
    click.echo(forecast.render(built))


@report.command("close")
@click.option("--month", default=None, help="the month to close, YYYY-MM")
@pass_shop
def close_report(shop: ShopContext, month: str | None) -> None:
    """The month end pack: work, money and what is coming."""
    stamped = parse_month(month) if month else StampedMonth.of(shop.today)
    with shop.open() as handle:
        pack = close.build(handle, stamped, shop.today)
    click.echo(close.render(pack))


@report.command("pack")
@click.argument("directory", type=click.Path(file_okay=False, path_type=Path))
@click.option("--from", "first", default=None, help="first day of the period")
@click.option("--to", "last", default=None, help="last day of the period")
@pass_shop
def audit_pack(shop: ShopContext, directory: Path, first: str | None, last: str | None) -> None:
    """Write an audit pack to a directory: a packet per cylinder and the sheets."""
    window = resolve_window(shop.today, first=first, last=last)
    with shop.open() as handle:
        result = pack.write(handle, directory, window.first, window.last, shop.today)
    click.echo(result.describe())
    for name in result.incomplete:
        click.echo(f"  incomplete: {name}")


@report.command("unbilled")
@click.option("--on", "day", default=None, help="the day to count up to")
@pass_shop
def unbilled_report(shop: ShopContext, day: str | None) -> None:
    """Work the shop has done and not charged for."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        found = unbilled.build(handle, when)
    click.echo(unbilled.render(found))


@report.command("ownership")
@click.option("--from", "first", default=None, help="first day of the window")
@click.option("--to", "last", default=None, help="last day of the window")
@pass_shop
def ownership_report(shop: ShopContext, first: str | None, last: str | None) -> None:
    """Cylinders that changed hands in a window."""
    window = resolve_window(shop.today, first=first, last=last)
    with shop.open() as handle:
        moves = TransferRepository(handle.connection).between(window.first, window.last)
    click.echo(str(window))
    echo_table(
        ["date", "cylinder", "from", "to", "note"],
        [
            [
                item.moved_on.isoformat(),
                item.cylinder_key,
                item.from_owner or "-",
                item.to_owner,
                item.note or "-",
            ]
            for item in moves
        ],
        empty="nothing changed hands",
    )


@report.command("gas")
@click.option("--from", "first", default=None, help="first day of the window")
@click.option("--to", "last", default=None, help="last day of the window")
@pass_shop
def gas_report(shop: ShopContext, first: str | None, last: str | None) -> None:
    """The fleet and the work, cut by what is in the cylinders."""
    window = resolve_window(shop.today, first=first, last=last)
    with shop.open() as handle:
        built = gases.build(handle, window.first, window.last)
    click.echo(str(window))
    click.echo(gases.render(built))


@report.command("cycle")
@click.option("--from", "first", default=None, help="first day of the window")
@click.option("--to", "last", default=None, help="last day of the window")
@pass_shop
def cycle_report(shop: ShopContext, first: str | None, last: str | None) -> None:
    """How long lots take to get through the shop."""
    window = resolve_window(shop.today, first=first, last=last)
    with shop.open() as handle:
        built = cycle.build(handle, window.first, window.last)
    click.echo(str(window))
    click.echo(cycle.render(built))


@report.command("worklist")
@click.option("--on", "day", default=None, help="the day to read it for")
@click.option("--due-within", default=3, show_default=True, help="months ahead for due dates")
@pass_shop
def worklist_report(shop: ShopContext, day: str | None, due_within: int) -> None:
    """Everything the shop owes somebody, on one list."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        built = WorklistService(handle).build(when, due_within=due_within)
    click.echo(built.describe())
