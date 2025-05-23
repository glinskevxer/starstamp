"""Commands that read the fleet rather than one cylinder.

Splitting these off is not tidiness for its own sake. The single cylinder
commands are the ones the bench runs forty times a day and they take a
cylinder key; these take a filter and answer about a set, and mixing the two
in one file meant every change to a listing risked the register command.
"""

from __future__ import annotations

from pathlib import Path

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.cli.cylinders import cylinder

__all__ = ["cylinder"]
from starstamp.cli.windows import parse_month
from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.reporting import life
from starstamp.service.imports import ImportService
from starstamp.store.cylinders import CylinderRepository
from starstamp.text.table import render_table


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
