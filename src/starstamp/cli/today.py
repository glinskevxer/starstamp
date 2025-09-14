"""The one command the shop runs before anything else.

Three questions get asked every morning and they are always the same three:
what is on the bench, what can we take today, and what do we owe somebody. The
answers already exist; this is the command that stops the shop needing to
remember which three commands they came from.
"""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.cli.output import echo_lines, echo_table
from starstamp.model.cylinder import CylinderKey
from starstamp.service.receiving import ReceivingService
from starstamp.service.repair import RepairService
from starstamp.service.schedule import ScheduleService
from starstamp.service.worklist import WorklistService


@click.command("today")
@click.option("--on", "day", default=None, help="pretend it is this day")
@click.option("--quiet", is_flag=True, help="leave out the bench sheet")
@pass_shop
def today(shop: ShopContext, day: str | None, quiet: bool) -> None:
    """What is on the bench, what the day can take, and what is owed."""
    when = resolve_day(day, shop)
    click.echo(when.strftime("%A %d %B %Y"))

    with shop.open() as handle:
        schedule = ScheduleService(handle)
        standing = schedule.capacity(when)
        rigs = schedule.working_rigs(when)
        promised = schedule.bookings.on_day(when)
        receiving = ReceivingService(handle)
        repairs = RepairService(handle)
        bench: list[list[str]] = []
        for lot in receiving.open_standing():
            for line in lot.lines:
                if line.is_settled:
                    continue
                key = CylinderKey.parse(line.cylinder_key)
                cylinder = receiving.cylinders.by_key(key)
                held = repairs.held_by(key)
                bench.append(
                    [
                        lot.lot.number,
                        str(key),
                        str(cylinder.specification),
                        cylinder.service.code,
                        "-" if held is None else "; ".join(held.reasons),
                    ]
                )
        outstanding = WorklistService(handle).build(when)

    click.echo("")
    click.echo(standing.describe())
    click.echo(f"rigs in calibration: {', '.join(rigs) if rigs else 'none'}")
    if promised:
        click.echo(
            "booked in: "
            + ", ".join(
                f"{item.owner_code} {item.cylinders}"
                for item in promised
                if item.state.holds_capacity
            )
        )

    if not quiet:
        click.echo("")
        echo_table(
            ["lot", "cylinder", "spec", "gas", "held for"],
            bench,
            empty="nothing on the bench",
        )

    click.echo("")
    if outstanding.is_clear:
        click.echo("nothing outstanding")
        return
    urgent = [item for item in outstanding.items if item.urgency == 0]
    echo_lines(
        (f"today: {item}" for item in urgent),
        empty=f"{len(outstanding.items)} things outstanding, none of them urgent",
    )
    if urgent:
        click.echo(f"{len(outstanding.items)} things outstanding in all")
