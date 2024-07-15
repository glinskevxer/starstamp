"""Reporting commands."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.model.cylinder import CylinderKey
from starstamp.model.dates import StampedMonth, parse_day
from starstamp.reporting import audit, throughput


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
    start = parse_day(first) if first else StampedMonth.of(shop.today).first_day()
    end = parse_day(last) if last else shop.today
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
