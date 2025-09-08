"""The reports about money rather than about cylinders.

Split off from the rest because they read a different half of the book and
because report.py had grown to the length where nobody scrolls to the bottom.
The commands still hang off the same group, so nothing changes for whoever
types them.
"""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.cli.report import report
from starstamp.cli.windows import parse_month
from starstamp.cli.windows import resolve as resolve_window
from starstamp.model.dates import StampedMonth
from starstamp.reporting import account as account_page
from starstamp.reporting import close, cycle, forecast, unbilled
from starstamp.text import machine

__all__ = ["report"]


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


@report.command("unbilled")
@click.option("--on", "day", default=None, help="the day to count up to")
@pass_shop
def unbilled_report(shop: ShopContext, day: str | None) -> None:
    """Work the shop has done and not charged for."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        found = unbilled.build(handle, when)
    click.echo(unbilled.render(found))


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


@report.command("account")
@click.argument("owner")
@click.option("--month", default=None, help="the month to state, YYYY-MM")
@pass_shop
def account_report(shop: ShopContext, owner: str, month: str | None) -> None:
    """One account on one page: fleet, money and what is in the shop."""
    window = resolve_window(shop.today, month=month)
    with shop.open() as handle:
        page = account_page.build(handle, owner, window.first, window.last, shop.today)
    click.echo(account_page.render(page))
