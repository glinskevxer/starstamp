"""Repair commands."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.model.cylinder import CylinderKey
from starstamp.model.repair import RepairKind
from starstamp.rules.repair import permitted_repairs
from starstamp.service.repair import RepairService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.repairs import RepairRepository
from starstamp.text.table import dash, render_table


@click.group()
def repair() -> None:
    """Work that is not a requalification."""


@repair.command("do")
@click.argument("key")
@click.argument("kind")
@click.option("--tech", required=True, help="who did it")
@click.option("--on", "day", default=None, help="the day it was done")
@click.option("--parts", default=None, help="what went in, for a valve change")
@click.option("--note", default=None)
@click.option("--rin", default=None, help="the number it was done under, where one is needed")
@pass_shop
def do_repair(
    shop: ShopContext,
    key: str,
    kind: str,
    tech: str,
    day: str | None,
    parts: str | None,
    note: str | None,
    rin: str | None,
) -> None:
    """Book a repair."""
    wanted = CylinderKey.parse(key)
    with shop.open_for_write() as handle:
        outcome = RepairService(handle).perform(
            wanted,
            RepairKind.parse(kind),
            resolve_day(day, shop),
            tech,
            parts=parts,
            note=note,
            facility_rin=rin,
        )
    click.echo(outcome.describe())


@repair.command("history")
@click.argument("key")
@pass_shop
def history(shop: ShopContext, key: str) -> None:
    """Every repair on a cylinder."""
    wanted = CylinderKey.parse(key)
    with shop.open() as handle:
        found = RepairRepository(handle.connection).for_cylinder(wanted)
    if not found:
        click.echo(f"no repairs on {wanted}")
        return
    click.echo(
        render_table(
            ["date", "repair", "tech", "rin", "parts", "note"],
            [
                [
                    item.performed_on.isoformat(),
                    item.kind.label,
                    item.technician_badge,
                    dash(item.facility_rin),
                    dash(item.parts),
                    dash(item.note),
                ]
                for item in found
            ],
        )
    )


@repair.command("options")
@click.argument("key")
@pass_shop
def options(shop: ShopContext, key: str) -> None:
    """What this cylinder may legally have done to it."""
    wanted = CylinderKey.parse(key)
    with shop.open() as handle:
        cylinder = CylinderRepository(handle.connection).by_key(wanted)
        service = RepairService(handle)
        held = service.held_by(wanted)
    allowed = sorted(item.label for item in permitted_repairs(cylinder))
    click.echo(f"{wanted} is a {cylinder.specification}")
    for item in allowed:
        click.echo(f"  {item}")
    if held is not None:
        click.echo(f"held since {held.performed_on.isoformat()}: " + "; ".join(held.reasons))


@repair.command("held")
@pass_shop
def held(shop: ShopContext) -> None:
    """Every cylinder sitting under a suspension."""
    from starstamp.model.cylinder import CylinderStatus

    with shop.open() as handle:
        cylinders = CylinderRepository(handle.connection).with_status(
            CylinderStatus.AWAITING_REPAIR
        )
        service = RepairService(handle)
        rows = []
        for cylinder in cylinders:
            event = service.held_by(cylinder.key)
            rows.append(
                [
                    str(cylinder.key),
                    cylinder.owner_code,
                    "-" if event is None else event.performed_on.isoformat(),
                    "-" if event is None else "; ".join(event.reasons),
                ]
            )
    if not rows:
        click.echo("nothing held")
        return
    click.echo(render_table(["cylinder", "owner", "since", "why"], rows))
