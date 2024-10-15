"""Cylinder commands: taking one onto the books and reading it back."""

from __future__ import annotations

from pathlib import Path

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.errors import RuleViolationError, ValidationError
from starstamp.model.cylinder import Cylinder, CylinderKey, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import parse_thousandths
from starstamp.model.service import lookup_service
from starstamp.model.specification import parse_specification
from starstamp.model.units import Expansion
from starstamp.rules.method_matrix import permitted_methods, required_test_pressure
from starstamp.service.imports import ImportService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.owners import OwnerRepository
from starstamp.text.table import dash, render_pairs, render_table


@click.group()
def cylinder() -> None:
    """Cylinders on the shop's books."""


@cylinder.command("register")
@click.argument("key")
@click.option("--owner", required=True, help="the account code the cylinder belongs to")
@click.option("--spec", required=True, help="the specification marking, DOT-3AA2015")
@click.option("--dom", required=True, help="date of manufacture as stamped, 06-98")
@click.option("--service", required=True, help="the gas it is in")
@click.option("--ree", default=None, help="rejection elastic expansion in cc, if marked")
@click.option("--water-capacity", default=None, type=float, help="water capacity in litres")
@click.option("--tare", default=None, type=float, help="tare weight in pounds")
@click.option("--wall", default=None, help="nominal wall in inches, 0.220")
@click.option("--wall-source", default="manufacturer data sheet", show_default=True)
@click.option("--on", "day", default=None, help="the day it was taken on, YYYY-MM-DD")
@pass_shop
def register(
    shop: ShopContext,
    key: str,
    owner: str,
    spec: str,
    dom: str,
    service: str,
    ree: str | None,
    water_capacity: float | None,
    tare: float | None,
    wall: str | None,
    wall_source: str,
    day: str | None,
) -> None:
    """Take a cylinder onto the books from its marks."""
    record = Cylinder(
        key=CylinderKey.parse(key),
        specification=parse_specification(spec),
        manufactured=StampedMonth.parse(dom),
        service=lookup_service(service),
        owner_code=owner.upper(),
        rejection_elastic_expansion=None if ree is None else Expansion.parse(ree),
        water_capacity_tenths_l=None if water_capacity is None else round(water_capacity * 10),
        tare_hundredths_lb=None if tare is None else round(tare * 100),
        nominal_wall_thousandths_in=None if wall is None else parse_thousandths(wall),
        wall_source=None if wall is None else wall_source,
    )
    with shop.open_for_write() as handle:
        owner_id = OwnerRepository(handle.connection).id_of(record.owner_code)
        CylinderRepository(handle.connection).add(record, owner_id, resolve_day(day, shop))
    click.echo(f"registered {record.key} for {record.owner_code}")


@cylinder.command("show")
@click.argument("key")
@pass_shop
def show(shop: ShopContext, key: str) -> None:
    """Show one cylinder as the book holds it."""
    wanted = CylinderKey.parse(key)
    with shop.open() as handle:
        found = CylinderRepository(handle.connection).by_key(wanted)
    methods = sorted(
        method.label for method in permitted_methods(found.specification, found.service)
    )
    try:
        pressure = str(required_test_pressure(found.specification))
    except (RuleViolationError, ValidationError):
        # A cylinder that is never pressure tested still has a page to show.
        pressure = "-"
    click.echo(
        render_pairs(
            [
                ("cylinder", str(found.key)),
                ("spec", str(found.specification)),
                ("made", found.manufactured.long_form()),
                ("service", found.service.name),
                ("owner", found.owner_code),
                ("status", found.status.value),
                ("ree", dash(found.rejection_elastic_expansion)),
                ("wall", dash(found.nominal_wall_thousandths_in)),
                ("test pressure", pressure),
                ("methods", ", ".join(methods) if methods else "-"),
            ]
        )
    )


@cylinder.command("list")
@click.option("--owner", default=None, help="only this account's cylinders")
@click.option("--status", "status_text", default=None, help="only cylinders in this status")
@pass_shop
def list_cylinders(shop: ShopContext, owner: str | None, status_text: str | None) -> None:
    """List cylinders."""
    with shop.open() as handle:
        repository = CylinderRepository(handle.connection)
        if owner is not None:
            found = repository.for_owner(owner.upper())
        elif status_text is not None:
            found = repository.with_status(CylinderStatus(status_text))
        else:
            found = [item for status in CylinderStatus for item in repository.with_status(status)]
    if not found:
        click.echo("no cylinders")
        return
    click.echo(
        render_table(
            ["cylinder", "spec", "service", "owner", "status"],
            [
                [
                    str(item.key),
                    str(item.specification),
                    item.service.code,
                    item.owner_code,
                    item.status.value,
                ]
                for item in sorted(found, key=lambda item: item.key)
            ],
        )
    )


@cylinder.command("wall")
@click.argument("key")
@click.argument("inches")
@click.option("--source", default="ultrasonic sweep", show_default=True)
@click.option("--note", default=None)
@click.option("--on", "day", default=None, help="the day it was measured, YYYY-MM-DD")
@pass_shop
def wall(
    shop: ShopContext, key: str, inches: str, source: str, note: str | None, day: str | None
) -> None:
    """Record a wall thickness reading."""
    wanted = CylinderKey.parse(key)
    thousandths = parse_thousandths(inches)
    with shop.open_for_write() as handle:
        CylinderRepository(handle.connection).record_wall(
            wanted, resolve_day(day, shop), thousandths, source, note
        )
    click.echo(f"{wanted} wall {inches} in from {source}")


@cylinder.command("transfer")
@click.argument("key")
@click.argument("owner")
@pass_shop
def transfer(shop: ShopContext, key: str, owner: str) -> None:
    """Move a cylinder to another account."""
    wanted = CylinderKey.parse(key)
    with shop.open_for_write() as handle:
        owner_id = OwnerRepository(handle.connection).id_of(owner)
        moved = CylinderRepository(handle.connection).transfer(wanted, owner_id)
    click.echo(f"{moved.key} now belongs to {moved.owner_code}")


@cylinder.command("status")
@click.argument("key")
@click.argument("status_text")
@pass_shop
def set_status(shop: ShopContext, key: str, status_text: str) -> None:
    """Move a cylinder between statuses."""
    wanted = CylinderKey.parse(key)
    try:
        status = CylinderStatus(status_text)
    except ValueError as exc:
        known = ", ".join(item.value for item in CylinderStatus)
        raise click.BadParameter(f"status is one of {known}") from exc
    with shop.open_for_write() as handle:
        moved = CylinderRepository(handle.connection).set_status(wanted, status)
    click.echo(f"{moved.key} is {moved.status.value}")


@cylinder.command("import")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--owner", required=True, help="the account the list belongs to")
@click.option("--on", "day", default=None, help="the day they came on the books")
@click.option("--write", is_flag=True, help="actually write them; without this it is a dry run")
@pass_shop
def import_list(shop: ShopContext, path: Path, owner: str, day: str | None, write: bool) -> None:
    """Take a customer's cylinder list into the book."""
    text = path.read_text()
    when = resolve_day(day, shop)
    if write:
        with shop.open_for_write() as handle:
            result = ImportService(handle).read(text, owner.upper(), when, write=True)
    else:
        with shop.open() as handle:
            result = ImportService(handle).read(text, owner.upper(), when, write=False)
    click.echo(result.describe())
    if not write and result.accepted:
        click.echo("nothing was written; pass --write to take them in")


@cylinder.command("template")
@click.option("--rows", default=1, show_default=True, help="how many example rows to print")
def template(rows: int) -> None:
    """Print a blank cylinder list for a customer to fill in.

    The columns after the fourth are optional, and the example row is filled
    in because a customer sent a list with the specification in the service
    column three times before this existed.
    """
    click.echo("cylinder,specification,manufactured,service,ree,wall")
    for index in range(max(rows, 0)):
        click.echo(f"NCI/A{4471 + index},DOT-3AA2015,06-98,N2,31.2,0.220")
