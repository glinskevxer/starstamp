"""Cylinder commands: taking one onto the books and reading it back."""

from __future__ import annotations

from pathlib import Path

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.cli.output import echo_lines
from starstamp.cli.windows import parse_month
from starstamp.errors import RuleViolationError, ValidationError
from starstamp.model.cylinder import Cylinder, CylinderKey, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import parse_thousandths
from starstamp.model.service import lookup_service
from starstamp.model.specification import parse_specification
from starstamp.model.units import Expansion
from starstamp.model.valve import outlet_for_service, parse_outlet
from starstamp.reporting import life
from starstamp.rules.method_matrix import permitted_methods, required_test_pressure
from starstamp.service.imports import ImportService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.owners import OwnerRepository
from starstamp.store.transfers import TransferRepository
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
@click.option("--valve", default=None, help="the CGA outlet fitted, 580")
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
    valve: str | None,
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
        valve_outlet=None if valve is None else parse_outlet(valve).number,
        valve_installed_on=None if valve is None else resolve_day(day, shop),
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
                (
                    "valve",
                    dash(None if found.valve_outlet is None else f"CGA {found.valve_outlet}"),
                ),
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
@click.option("--on", "day", default=None, help="the day it changed hands")
@click.option("--note", default=None, help="why, or what paperwork covers it")
@pass_shop
def transfer(shop: ShopContext, key: str, owner: str, day: str | None, note: str | None) -> None:
    """Move a cylinder to another account."""
    wanted = CylinderKey.parse(key)
    with shop.open_for_write() as handle:
        owner_id = OwnerRepository(handle.connection).id_of(owner)
        moved = CylinderRepository(handle.connection).transfer(
            wanted, owner_id, resolve_day(day, shop), note
        )
    click.echo(f"{moved.key} now belongs to {moved.owner_code}")


@cylinder.command("owners")
@click.argument("key")
@pass_shop
def owners_history(shop: ShopContext, key: str) -> None:
    """Who has owned a cylinder."""
    wanted = CylinderKey.parse(key)
    with shop.open() as handle:
        current = CylinderRepository(handle.connection).by_key(wanted)
        moves = TransferRepository(handle.connection).for_cylinder(wanted)
    click.echo(f"{wanted} belongs to {current.owner_code}")
    echo_lines((item.summary() for item in moves), empty="it has never changed hands here")


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


@cylinder.command("valve")
@click.argument("key")
@click.argument("outlet", required=False)
@click.option("--on", "day", default=None, help="the day it was fitted")
@pass_shop
def valve(shop: ShopContext, key: str, outlet: str | None, day: str | None) -> None:
    """Record the valve fitted, or say which one the gas calls for."""
    wanted = CylinderKey.parse(key)
    with shop.open() as handle:
        found = CylinderRepository(handle.connection).by_key(wanted)
    if outlet is None:
        needed = outlet_for_service(found.service.code)
        fitted = "none recorded" if found.valve_outlet is None else f"CGA {found.valve_outlet}"
        click.echo(f"{wanted} in {found.service}: fitted {fitted}, takes {needed}")
        return
    fitting = parse_outlet(outlet)
    with shop.open_for_write() as handle:
        updated = CylinderRepository(handle.connection).fit_valve(
            wanted, fitting.number, resolve_day(day, shop)
        )
    click.echo(f"{updated.key} fitted with {fitting} on {updated.valve_installed_on}")


@cylinder.command("service")
@click.argument("key")
@click.argument("gas")
@pass_shop
def change_service(shop: ShopContext, key: str, gas: str) -> None:
    """Put a cylinder into another gas. The valve comes off with the old one."""
    wanted = CylinderKey.parse(key)
    service = lookup_service(gas)
    with shop.open_for_write() as handle:
        moved = CylinderRepository(handle.connection).change_service(wanted, service)
    needed = outlet_for_service(moved.service.code)
    click.echo(f"{moved.key} is now in {moved.service} service and needs {needed}")


@cylinder.command("life")
@click.argument("key")
@click.option("--only", default=None, help="one kind of entry: test, repair, notice, wall")
@pass_shop
def cylinder_life(shop: ShopContext, key: str, only: str | None) -> None:
    """Everything the book holds about one cylinder, in order."""
    wanted = CylinderKey.parse(key)
    with shop.open() as handle:
        built = life.build(handle, wanted)
    if only is None:
        click.echo(life.render(built, shop.today))
        return
    entries = built.of_kind(only.strip().lower())
    if not entries:
        click.echo(f"nothing of that kind for {wanted}")
        return
    for entry in entries:
        click.echo(f"{entry.day.isoformat()}  {entry.reference or '-'}  {entry.detail}")


@cylinder.command("age")
@click.option("--owner", default=None, help="only this account's cylinders")
@pass_shop
def age_profile(shop: ShopContext, owner: str | None) -> None:
    """How old the fleet is, by decade of manufacture."""
    with shop.open() as handle:
        repository = CylinderRepository(handle.connection)
        if owner is not None:
            fleet = repository.for_owner(owner.upper())
        else:
            fleet = [item for status in CylinderStatus for item in repository.with_status(status)]
    if not fleet:
        click.echo("no cylinders")
        return
    counts: dict[str, int] = {}
    for item in fleet:
        decade = (item.manufactured.year // 10) * 10
        counts[f"{decade}s"] = counts.get(f"{decade}s", 0) + 1
    click.echo(
        render_table(
            ["made", "cylinders"],
            [[label, str(count)] for label, count in sorted(counts.items())],
            right=(1,),
        )
    )
    oldest = min(fleet, key=lambda item: (item.manufactured.year, item.manufactured.month))
    years = shop.today.year - oldest.manufactured.year
    click.echo(f"oldest is {oldest.key}, made {oldest.manufactured.long_form()}, {years} years")


@cylinder.command("find")
@click.option("--owner", default=None, help="one account")
@click.option("--status", "status_text", default=None, help="one status")
@click.option("--service", "service_code", default=None, help="one gas")
@click.option("--spec", "spec_code", default=None, help="one specification code, 3AA")
@click.option("--maker", default=None, help="one manufacturer symbol")
@click.option("--made-before", default=None, help="made before this month, YYYY-MM")
@click.option("--made-after", default=None, help="made after this month, YYYY-MM")
@click.option("--limit", default=None, type=int, help="stop after this many")
@pass_shop
def find(
    shop: ShopContext,
    owner: str | None,
    status_text: str | None,
    service_code: str | None,
    spec_code: str | None,
    maker: str | None,
    made_before: str | None,
    made_after: str | None,
    limit: int | None,
) -> None:
    """Find cylinders by whatever you happen to know about them."""
    status = None
    if status_text is not None:
        try:
            status = CylinderStatus(status_text)
        except ValueError as exc:
            known = ", ".join(item.value for item in CylinderStatus)
            raise click.BadParameter(f"status is one of {known}") from exc
    with shop.open() as handle:
        found = CylinderRepository(handle.connection).search(
            owner_code=owner,
            status=status,
            service_code=service_code,
            spec_code=spec_code,
            symbol=maker,
            made_before=None if made_before is None else parse_month(made_before),
            made_after=None if made_after is None else parse_month(made_after),
            limit=limit,
        )
    if not found:
        click.echo("nothing matches")
        return
    click.echo(
        render_table(
            ["cylinder", "spec", "gas", "made", "owner", "status"],
            [
                [
                    str(item.key),
                    str(item.specification),
                    item.service.code,
                    item.manufactured.long_form(),
                    item.owner_code,
                    item.status.value,
                ]
                for item in found
            ],
        )
    )
    click.echo(f"{len(found)} cylinders")
