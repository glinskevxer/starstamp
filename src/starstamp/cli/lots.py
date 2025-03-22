"""Receiving commands: the front counter's day."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.model.cylinder import CylinderKey
from starstamp.model.lot import LotStatus
from starstamp.model.settings import STORAGE_FREE_DAYS
from starstamp.rules.storage import chargeable
from starstamp.service.abandoned import AbandonedService
from starstamp.service.receiving import ReceivingService
from starstamp.store.lots import LotRepository
from starstamp.store.settings import SettingRepository
from starstamp.text.table import dash, render_pairs, render_table


@click.group()
def lot() -> None:
    """Receiving lots."""


@lot.command("receive")
@click.argument("owner")
@click.argument("keys", nargs=-1, required=True)
@click.option("--on", "day", default=None, help="the day it arrived")
@click.option("--promised", default=None, help="the day it was promised back")
@click.option("--carrier", default=None)
@click.option("--note", default=None)
@pass_shop
def receive(
    shop: ShopContext,
    owner: str,
    keys: tuple[str, ...],
    day: str | None,
    promised: str | None,
    carrier: str | None,
    note: str | None,
) -> None:
    """Book a delivery in."""
    when = resolve_day(day, shop)
    with shop.open_for_write() as handle:
        standing = ReceivingService(handle).receive(
            owner.upper(),
            when,
            [CylinderKey.parse(item) for item in keys],
            promised_on=None if promised is None else resolve_day(promised, shop),
            carrier=carrier,
            note=note,
        )
    click.echo(f"{standing.lot.number} received, {len(standing.lines)} cylinders")


@lot.command("show")
@click.argument("number")
@pass_shop
def show(shop: ShopContext, number: str) -> None:
    """Show a lot and everything on it."""
    with shop.open() as handle:
        standing = ReceivingService(handle).standing(number)
    found = standing.lot
    click.echo(
        render_pairs(
            [
                ("lot", found.number),
                ("owner", found.owner_code),
                ("received", found.received_on.isoformat()),
                ("promised", dash(found.promised_on)),
                ("status", found.status.value),
                ("carrier", dash(found.carrier)),
                ("returned", dash(found.returned_on)),
                ("in shop", f"{found.days_in_shop(shop.today)} days"),
            ]
        )
    )
    if standing.lines:
        click.echo("")
        click.echo(
            render_table(
                ["cylinder", "added", "disposition", "record"],
                [
                    [
                        line.cylinder_key,
                        line.added_on.isoformat(),
                        dash(line.disposition),
                        dash(line.event_id),
                    ]
                    for line in standing.lines
                ],
            )
        )


@lot.command("open")
@pass_shop
def open_lots(shop: ShopContext) -> None:
    """Every lot still in the shop."""
    with shop.open() as handle:
        standings = ReceivingService(handle).open_standing()
    if not standings:
        click.echo("nothing in the shop")
        return
    click.echo(
        render_table(
            ["lot", "owner", "received", "promised", "status", "settled", "days"],
            [
                [
                    standing.lot.number,
                    standing.lot.owner_code,
                    standing.lot.received_on.isoformat(),
                    dash(standing.lot.promised_on),
                    standing.lot.status.value,
                    f"{standing.settled}/{len(standing.lines)}",
                    str(standing.lot.days_in_shop(shop.today)),
                ]
                for standing in standings
            ],
            right=(6,),
        )
    )
    late = [standing for standing in standings if standing.lot.is_late(shop.today)]
    for standing in late:
        click.echo(f"late: {standing.describe(shop.today)}")


@lot.command("add")
@click.argument("number")
@click.argument("keys", nargs=-1, required=True)
@click.option("--on", "day", default=None)
@pass_shop
def add_to_lot(shop: ShopContext, number: str, keys: tuple[str, ...], day: str | None) -> None:
    """Put more cylinders on a lot that is already open."""
    when = resolve_day(day, shop)
    with shop.open_for_write() as handle:
        service = ReceivingService(handle)
        for item in keys:
            parsed = CylinderKey.parse(item)
            service.lots.add_line(number, service.cylinders.id_of(parsed), parsed, when)
    click.echo(f"{len(keys)} added to {number.upper()}")


@lot.command("ready")
@click.argument("number")
@pass_shop
def ready(shop: ShopContext, number: str) -> None:
    """Say a lot is finished and ready to go back."""
    with shop.open_for_write() as handle:
        standing = ReceivingService(handle).ready(number)
    click.echo(f"{standing.lot.number} is ready, {standing.settled} cylinders settled")


@lot.command("return")
@click.argument("number")
@click.option("--on", "day", default=None)
@pass_shop
def return_lot(shop: ShopContext, number: str, day: str | None) -> None:
    """Send a lot back to its owner."""
    when = resolve_day(day, shop)
    with shop.open_for_write() as handle:
        standing = ReceivingService(handle).return_lot(number, when)
    click.echo(
        f"{standing.lot.number} went back on {when.isoformat()} after "
        f"{standing.lot.days_in_shop(when)} days"
    )


@lot.command("history")
@click.argument("owner")
@pass_shop
def lot_history(shop: ShopContext, owner: str) -> None:
    """Every lot an account has sent in."""
    with shop.open() as handle:
        found = LotRepository(handle.connection).for_owner(owner)
    if not found:
        click.echo(f"no lots for {owner.upper()}")
        return
    click.echo(
        render_table(
            ["lot", "received", "returned", "status", "days"],
            [
                [
                    item.number,
                    item.received_on.isoformat(),
                    dash(item.returned_on),
                    item.status.value,
                    str(item.days_in_shop(shop.today)),
                ]
                for item in found
            ],
            right=(4,),
        )
    )
    finished = [item for item in found if item.status is LotStatus.RETURNED]
    if finished:
        average = sum(item.days_in_shop(shop.today) for item in finished) / len(finished)
        click.echo(f"{len(finished)} returned, {average:.1f} days on average")


@lot.command("storage")
@click.option("--on", "day", default=None, help="the day to count to")
@click.option("--owner", default=None, help="only this account")
@pass_shop
def storage(shop: ShopContext, day: str | None, owner: str | None) -> None:
    """Lots that have been in the way longer than the free period."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        repository = LotRepository(handle.connection)
        found = repository.for_owner(owner) if owner else repository.open_lots()
        free_days = SettingRepository(handle.connection).integer(STORAGE_FREE_DAYS, when)
        charging = chargeable(found, when, free_days)
    if not charging:
        click.echo(f"nothing has been here longer than {free_days} days")
        return
    click.echo(
        render_table(
            ["lot", "owner", "received", "held", "chargeable"],
            [
                [
                    item.lot_number,
                    item.owner_code,
                    item.received_on.isoformat(),
                    str(item.days_held),
                    str(item.chargeable_days),
                ]
                for item in charging
            ],
            right=(3, 4),
        )
    )


@lot.command("uncollected")
@click.option("--on", "day", default=None, help="the day to read it for")
@click.option("--write", is_flag=True, help="write to the accounts that are overdue")
@pass_shop
def uncollected(shop: ShopContext, day: str | None, write: bool) -> None:
    """Lots that are ready and that nobody has come for."""
    when = resolve_day(day, shop)
    if write:
        with shop.open_for_write() as handle:
            service = AbandonedService(handle)
            overdue = service.needing_a_letter(when)
            for item in overdue:
                service.write_to(item.lot.number, when)
        click.echo(f"wrote to {len(overdue)} accounts")
        return
    with shop.open() as handle:
        found = AbandonedService(handle).left_behind(when)
    if not found:
        click.echo("nothing is waiting to be collected")
        return
    click.echo(
        render_table(
            ["lot", "owner", "ready", "standing", "next step"],
            [
                [
                    item.lot.number,
                    item.lot.owner_code,
                    str(item.standing.days_ready),
                    item.standing.standing.value,
                    dash(item.standing.next_step_on()),
                ]
                for item in found
            ],
            right=(2,),
        )
    )
    for item in found:
        if item.standing.standing.may_be_disposed_of:
            click.echo(f"abandoned: {item.describe()}")
