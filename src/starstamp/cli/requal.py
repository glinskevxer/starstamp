"""Requalification commands: the ones the bench actually types."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.errors import ValidationError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind, Observation, parse_thousandths
from starstamp.model.method import Method
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion, Pressure
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.events import EventRepository
from starstamp.text.table import dash, render_pairs, render_table


def parse_defect(text: str) -> Observation:
    """Read a defect off the command line: kind[:depth[:length[:note]]].

    The bench types these one after another and the depth is in inches, the
    way the gauge reads. Everything after the length is a free note.
    """
    parts = text.split(":")
    kind = DefectKind.parse(parts[0])
    depth = parse_thousandths(parts[1]) if len(parts) > 1 and parts[1] else None
    length = parse_thousandths(parts[2]) if len(parts) > 2 and parts[2] else None
    note = parts[3] if len(parts) > 3 and parts[3] else None
    return Observation(
        kind=kind, depth_thousandths_in=depth, length_thousandths_in=length, note=note
    )


def build_readings(
    applied: str | None,
    hold: int,
    total: str | None,
    permanent: str | None,
    leaked: bool,
    distorted: bool,
) -> PressureReadings | None:
    if applied is None:
        if total is not None or permanent is not None:
            raise ValidationError("expansion readings need the pressure they were taken at")
        return None
    return PressureReadings(
        applied=Pressure.parse(applied),
        hold_seconds=hold,
        total_expansion=None if total is None else Expansion.parse(total),
        permanent_expansion=None if permanent is None else Expansion.parse(permanent),
        leaked=leaked,
        distorted=distorted,
    )


@click.group()
def requal() -> None:
    """Requalifications."""


@requal.command("run")
@click.argument("key")
@click.option("--tech", required=True, help="the badge of whoever did the work")
@click.option("--method", "method_text", default=None, help="leave out to let the shop choose")
@click.option("--system", "system_code", default=None, help="the test system used")
@click.option("--on", "day", default=None, help="the day of the test, YYYY-MM-DD")
@click.option("--applied", default=None, help="the pressure reached, psig")
@click.option("--hold", default=30, show_default=True, help="hold time in seconds")
@click.option("--total", default=None, help="total expansion in cc")
@click.option("--permanent", default=None, help="permanent expansion in cc")
@click.option("--leaked", is_flag=True, help="the cylinder leaked under pressure")
@click.option("--distorted", is_flag=True, help="the cylinder took a visible set")
@click.option(
    "--defect",
    "defects",
    multiple=True,
    help="kind:depth:length:note, repeat for each condition found",
)
@click.option("--rin", default=None, help="name the RIN when the book holds more than one")
@pass_shop
def run_requalification(
    shop: ShopContext,
    key: str,
    tech: str,
    method_text: str | None,
    system_code: str | None,
    day: str | None,
    applied: str | None,
    hold: int,
    total: str | None,
    permanent: str | None,
    leaked: bool,
    distorted: bool,
    defects: tuple[str, ...],
    rin: str | None,
) -> None:
    """Requalify a cylinder and write the record of test."""
    request = RequalificationRequest(
        key=CylinderKey.parse(key),
        day=resolve_day(day, shop),
        technician_badge=tech,
        method=None if method_text is None else Method.parse(method_text),
        system_code=system_code,
        observations=tuple(parse_defect(item) for item in defects),
        readings=build_readings(applied, hold, total, permanent, leaked, distorted),
        facility_rin=rin,
    )
    with shop.open_for_write() as handle:
        result = RequalificationService(handle).perform(request)
    click.echo(result.summary())
    for reason in result.event.reasons:
        click.echo(f"  {reason}")
    if not result.star.granted and result.event.outcome.may_be_marked:
        click.echo(f"  no star: {result.star.refusals[0]}")


@requal.command("history")
@click.argument("key")
@click.option("--all", "show_all", is_flag=True, help="include reversed records")
@pass_shop
def history(shop: ShopContext, key: str, show_all: bool) -> None:
    """Show every record of test for a cylinder."""
    wanted = CylinderKey.parse(key)
    with shop.open() as handle:
        events = EventRepository(handle.connection).for_cylinder(wanted, standing_only=not show_all)
    if not events:
        click.echo(f"no records of test for {wanted}")
        return
    click.echo(
        render_table(
            ["date", "method", "outcome", "rin", "tech", "state"],
            [
                [
                    event.performed_on.isoformat(),
                    event.method.label,
                    event.outcome.value,
                    event.facility_rin,
                    event.technician_badge,
                    event.state.value,
                ]
                for event in events
            ],
        )
    )


@requal.command("show")
@click.argument("event_id", type=int)
@pass_shop
def show_event(shop: ShopContext, event_id: int) -> None:
    """Show one record of test in full."""
    with shop.open() as handle:
        repository = EventRepository(handle.connection)
        event = repository.by_id(event_id)
        findings = repository.observations(event_id)
    readings = event.readings
    click.echo(
        render_pairs(
            [
                ("record", str(event_id)),
                ("cylinder", str(event.cylinder)),
                ("date", event.performed_on.isoformat()),
                ("method", event.method.label),
                ("rin", event.facility_rin),
                ("technician", event.technician_badge),
                ("system", dash(event.system_code)),
                ("outcome", event.outcome.value),
                ("state", event.state.value),
                ("readings", dash(None if readings is None else readings.describe())),
            ]
        )
    )
    for observation, result, reason in findings:
        click.echo(f"  {result.value}: {observation.describe()} ({reason})")
    for reason in event.reasons:
        click.echo(f"  {reason}")
