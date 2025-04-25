"""Booking commands, for the person answering the phone."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.cli.output import echo_lines, echo_table
from starstamp.service.schedule import ScheduleService
from starstamp.store.bookings import BookingRepository
from starstamp.text.table import dash, render_table


@click.group()
def book() -> None:
    """Work promised for a day."""


@book.command("in")
@click.argument("owner")
@click.argument("cylinders", type=int)
@click.option("--for", "day", required=True, help="the day it is promised for")
@click.option("--note", default=None)
@pass_shop
def book_in(shop: ShopContext, owner: str, cylinders: int, day: str, note: str | None) -> None:
    """Promise a day's work to an account."""
    when = resolve_day(day, shop)
    with shop.open_for_write() as handle:
        booking = ScheduleService(handle).book_in(
            owner.upper(), when, cylinders, shop.today, note=note
        )
    click.echo(f"booked {booking.summary()}")


@book.command("day")
@click.option("--on", "day", default=None, help="the day to read")
@pass_shop
def day_view(shop: ShopContext, day: str | None) -> None:
    """What is promised for a day, and what is left."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        service = ScheduleService(handle)
        standing = service.capacity(when)
        rigs = service.working_rigs(when)
        promised = service.bookings.on_day(when)
    click.echo(standing.describe())
    click.echo(f"rigs in calibration: {', '.join(rigs) if rigs else 'none'}")
    echo_table(
        ["id", "owner", "cylinders", "state", "lot"],
        [
            [
                str(item.booking_id),
                item.owner_code,
                str(item.cylinders),
                item.state.value,
                dash(item.lot_number),
            ]
            for item in promised
        ],
        right=(2,),
        empty="nothing promised",
    )


@book.command("week")
@click.option("--from", "day", default=None, help="the first day of the week to show")
@pass_shop
def week(shop: ShopContext, day: str | None) -> None:
    """The next seven days, with what is free on each."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        days = ScheduleService(handle).week(when)
    click.echo(
        render_table(
            ["day", "capacity", "booked", "free"],
            [
                [
                    standing.day.isoformat(),
                    str(standing.capacity),
                    str(standing.booked),
                    str(standing.free),
                ]
                for standing in days
            ],
            right=(1, 2, 3),
        )
    )
    for standing in days:
        if standing.is_over:
            click.echo(f"oversold: {standing.describe()}")


@book.command("offer")
@click.argument("cylinders", type=int)
@click.option("--from", "day", default=None, help="the first day to look at")
@click.option("--within", default=14, show_default=True, help="how many days ahead to look")
@pass_shop
def offer(shop: ShopContext, cylinders: int, day: str | None, within: int) -> None:
    """The next days that could take a given number of cylinders."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        found = ScheduleService(handle).offers(when, within, cylinders)
    echo_lines(
        (item.describe() for item in found[:5]),
        empty=f"no day in the next {within} could take {cylinders}",
    )


@book.command("arrive")
@click.argument("booking_id", type=int)
@click.argument("lot_number")
@pass_shop
def arrive(shop: ShopContext, booking_id: int, lot_number: str) -> None:
    """Tie a booking to the lot that turned up against it."""
    with shop.open_for_write() as handle:
        booking = ScheduleService(handle).arrive(booking_id, lot_number)
    click.echo(f"{booking.summary()}")


@book.command("cancel")
@click.argument("booking_id", type=int)
@click.option("--note", default=None)
@pass_shop
def cancel(shop: ShopContext, booking_id: int, note: str | None) -> None:
    """Cancel a booking and give the room back."""
    with shop.open_for_write() as handle:
        booking = BookingRepository(handle.connection).cancel(booking_id, note)
    click.echo(f"cancelled {booking.summary()}")


@book.command("missed")
@click.option("--on", "day", default=None)
@pass_shop
def missed(shop: ShopContext, day: str | None) -> None:
    """Bookings whose day has gone and whose cylinders never came."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        found = BookingRepository(handle.connection).missed(when)
    echo_lines(
        (f"{item.summary()}, {abs(item.days_out(when))} days ago" for item in found),
        empty="nothing missed",
    )
