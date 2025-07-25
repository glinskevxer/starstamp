"""Commands for restoring marks a cylinder has worn off."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.cli.output import echo_table
from starstamp.errors import ValidationError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.marking import Evidence, MarkKind, RestoredMark, normalise_mark
from starstamp.service.remark import RemarkService


def parse_mark(text: str) -> RestoredMark:
    """Read a mark off the command line: kind=what it reads."""
    kind, separator, reads = text.partition("=")
    if not separator or not reads.strip():
        raise ValidationError(f"a mark is KIND=READING, got {text!r}")
    cleaned = kind.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "spec": MarkKind.SPECIFICATION,
        "maker": MarkKind.MANUFACTURER,
        "dom": MarkKind.MANUFACTURE_DATE,
        "pressure": MarkKind.SERVICE_PRESSURE,
        "ree": MarkKind.REJECTION_LIMIT,
        "tare": MarkKind.TARE_WEIGHT,
    }
    if cleaned in aliases:
        return RestoredMark(aliases[cleaned], normalise_mark(reads))
    try:
        return RestoredMark(MarkKind(cleaned), normalise_mark(reads))
    except ValueError as exc:
        known = ", ".join(item.value for item in MarkKind)
        raise ValidationError(f"a mark is one of {known}, not {kind!r}") from exc


def parse_evidence(text: str) -> Evidence:
    cleaned = text.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {"ours": Evidence.OUR_RECORDS, "owner": Evidence.OWNER_DECLARATION}
    if cleaned in aliases:
        return aliases[cleaned]
    try:
        return Evidence(cleaned)
    except ValueError as exc:
        known = ", ".join(item.value for item in Evidence)
        raise ValidationError(f"evidence is one of {known}, not {text!r}") from exc


@click.group()
def remark() -> None:
    """Marks restored to a cylinder."""


@remark.command("stamp")
@click.argument("key")
@click.option("--mark", "marks", multiple=True, required=True, help="KIND=READING, repeat")
@click.option("--from", "evidence", required=True, help="ours, owner or manufacturer_letter")
@click.option("--tech", required=True, help="who stamped it")
@click.option("--on", "day", default=None)
@click.option("--rin", default=None, help="name the RIN when the book holds more than one")
@click.option("--note", default=None)
@pass_shop
def stamp(
    shop: ShopContext,
    key: str,
    marks: tuple[str, ...],
    evidence: str,
    tech: str,
    day: str | None,
    rin: str | None,
    note: str | None,
) -> None:
    """Restore marks to a cylinder, from evidence the shop can show."""
    wanted = CylinderKey.parse(key)
    with shop.open_for_write() as handle:
        outcome = RemarkService(handle).restore(
            wanted,
            tuple(parse_mark(item) for item in marks),
            parse_evidence(evidence),
            resolve_day(day, shop),
            tech,
            facility_rin=rin,
            note=note,
        )
    click.echo(outcome.describe())


@remark.command("history")
@click.argument("key")
@pass_shop
def history(shop: ShopContext, key: str) -> None:
    """Every re-marking on a cylinder."""
    wanted = CylinderKey.parse(key)
    with shop.open() as handle:
        found = RemarkService(handle).history(wanted)
    echo_table(
        ["date", "rin", "tech", "from", "marks"],
        [
            [
                item.marked_on.isoformat(),
                item.facility_rin,
                item.technician_badge,
                item.evidence.label,
                ", ".join(str(mark) for mark in item.marks),
            ]
            for item in found
        ],
        empty=f"{wanted} has never been re-marked here",
    )


@remark.command("available")
@click.argument("key")
@pass_shop
def available(shop: ShopContext, key: str) -> None:
    """What the book could stand behind if this cylinder needed re-marking."""
    wanted = CylinderKey.parse(key)
    with shop.open() as handle:
        service = RemarkService(handle)
        found = service.what_we_could_restore(wanted)
        records = len(service.events.for_cylinder(wanted, standing_only=True))
    click.echo(f"{wanted}, {records} standing records of test here")
    echo_table(
        ["mark", "reads"],
        [[kind.label, reads] for kind, reads in sorted(found.items(), key=lambda p: p[0].value)],
        empty="the book holds nothing that could be restored",
    )
