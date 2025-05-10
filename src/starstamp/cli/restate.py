"""Restatement commands.

These are the ones nobody wants to type. They exist so that the shop has a
way to say it was wrong that does not involve editing anything.
"""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop
from starstamp.model.calibration import InstrumentKind, normalise_system_code
from starstamp.model.dates import parse_day
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion, Pressure
from starstamp.service.restate import CorrectionService, RestatementService
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.events import EventRepository
from starstamp.text.table import render_table


@click.group()
def restate() -> None:
    """Reversals and replacements."""


@restate.command("certificate")
@click.argument("system_code")
@click.argument("instrument")
@click.argument("serial")
@click.argument("corrected_until")
@click.option("--reason", required=True, help="what the calibration house said")
@click.option("--dry-run", is_flag=True, help="show what would be pulled and write nothing")
@pass_shop
def restate_certificate(
    shop: ShopContext,
    system_code: str,
    instrument: str,
    serial: str,
    corrected_until: str,
    reason: str,
    dry_run: bool,
) -> None:
    """Shorten a certificate and pull the work it no longer covers."""
    system = normalise_system_code(system_code)
    kind = InstrumentKind.parse(instrument)
    until = parse_day(corrected_until)
    if dry_run:
        with shop.open() as handle:
            calibration = CalibrationRepository(handle.connection)
            certificate = calibration.by_id(calibration.id_of(system, kind, serial))
            from datetime import timedelta

            affected = RestatementService(handle).affected(
                system, until + timedelta(days=1), certificate.valid_until
            )
        click.echo(f"{len(affected)} records would be reversed")
        for event in affected:
            click.echo(f"  {event.summary()}")
        return

    with shop.open_for_write() as handle:
        calibration = CalibrationRepository(handle.connection)
        certificate_id = calibration.id_of(system, kind, serial)
        result = RestatementService(handle).restate_certificate(certificate_id, until, reason)
    click.echo(result.describe())
    for event in result.replacements:
        click.echo(f"  {event.cylinder} {event.performed_on} is no longer requalified")


@restate.command("reverse")
@click.argument("event_id", type=int)
@click.option("--reason", required=True, help="why the record is being pulled")
@pass_shop
def reverse_one(shop: ShopContext, event_id: int, reason: str) -> None:
    """Reverse a single record of test."""
    with shop.open_for_write() as handle:
        reversed_event = EventRepository(handle.connection).reverse(event_id, reason)
    click.echo(f"reversed {event_id}: {reversed_event.summary()}")


@restate.command("window")
@click.argument("system_code")
@click.argument("first")
@click.argument("last")
@pass_shop
def window(shop: ShopContext, system_code: str, first: str, last: str) -> None:
    """List the standing records a rig produced between two days."""
    with shop.open() as handle:
        events = RestatementService(handle).affected(
            normalise_system_code(system_code), parse_day(first), parse_day(last)
        )
    if not events:
        click.echo("nothing in that window")
        return
    click.echo(
        render_table(
            ["record", "date", "cylinder", "method", "outcome"],
            [
                [
                    str(event.event_id),
                    event.performed_on.isoformat(),
                    str(event.cylinder),
                    event.method.label,
                    event.outcome.value,
                ]
                for event in events
            ],
        )
    )


@restate.command("correct")
@click.argument("event_id", type=int)
@click.option("--reason", required=True, help="what was written down wrong")
@click.option("--applied", default=None, help="the corrected pressure, psig")
@click.option("--total", default=None, help="the corrected total expansion")
@click.option("--permanent", default=None, help="the corrected permanent expansion")
@click.option("--hold", default=30, show_default=True, help="hold time in seconds")
@click.option("--tech", default=None, help="the badge it should have been against")
@click.option("--system", "system_code", default=None, help="the rig it should have been")
@pass_shop
def correct(
    shop: ShopContext,
    event_id: int,
    reason: str,
    applied: str | None,
    total: str | None,
    permanent: str | None,
    hold: int,
    tech: str | None,
    system_code: str | None,
) -> None:
    """Reverse a record and rewrite it with the numbers it should have had."""
    readings = None
    if applied is not None:
        readings = PressureReadings(
            applied=Pressure.parse(applied),
            hold_seconds=hold,
            total_expansion=None if total is None else Expansion.parse(total),
            permanent_expansion=None if permanent is None else Expansion.parse(permanent),
        )
    with shop.open_for_write() as handle:
        corrected = CorrectionService(handle).correct(
            event_id,
            reason,
            readings=readings,
            technician_badge=tech,
            system_code=system_code,
        )
    click.echo(corrected.describe())
