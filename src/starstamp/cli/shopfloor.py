"""Commands for the shop's own approvals: the RIN, the bench and the rigs."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.model.calibration import (
    Certificate,
    InstrumentKind,
    SystemCheck,
    normalise_system_code,
)
from starstamp.model.dates import parse_day
from starstamp.model.facility import Facility, Technician, normalise_badge, normalise_rin
from starstamp.model.method import Method
from starstamp.model.units import Expansion
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.facility import FacilityRepository, TechnicianRepository
from starstamp.text.table import dash, render_pairs, render_table, yes_no


def parse_methods(text: str) -> frozenset[Method]:
    return frozenset(Method.parse(item) for item in text.split(",") if item.strip())


@click.group()
def facility() -> None:
    """The shop's own identification number."""


@facility.command("add")
@click.argument("rin")
@click.argument("name")
@click.option("--from", "approved_from", required=True, help="the day the RIN was issued")
@click.option("--until", "approved_until", required=True, help="the day it expires")
@click.option("--methods", required=True, help="comma separated, volumetric,proof,visual")
@click.option("--address", default=None)
@pass_shop
def add_facility(
    shop: ShopContext,
    rin: str,
    name: str,
    approved_from: str,
    approved_until: str,
    methods: str,
    address: str | None,
) -> None:
    """Record the shop's approval."""
    record = Facility(
        rin=normalise_rin(rin),
        name=name,
        approved_from=parse_day(approved_from),
        approved_until=parse_day(approved_until),
        methods=parse_methods(methods),
        address=address,
    )
    with shop.open_for_write() as handle:
        FacilityRepository(handle.connection).add(record)
    click.echo(f"recorded {record}")


@facility.command("show")
@click.option("--rin", default=None)
@pass_shop
def show_facility(shop: ShopContext, rin: str | None) -> None:
    """Show the shop's approval and what it covers."""
    with shop.open() as handle:
        repository = FacilityRepository(handle.connection)
        found = repository.by_rin(rin) if rin else repository.only()
    click.echo(
        render_pairs(
            [
                ("rin", found.rin),
                ("name", found.name),
                ("address", dash(found.address)),
                ("approved", f"{found.approved_from} to {found.approved_until}"),
                ("in force", yes_no(found.approved_on(shop.today))),
                ("methods", ", ".join(sorted(method.label for method in found.methods))),
            ]
        )
    )


@facility.command("renew")
@click.argument("rin")
@click.argument("until")
@pass_shop
def renew_facility(shop: ShopContext, rin: str, until: str) -> None:
    """Move a RIN's expiry out."""
    parse_day(until)
    with shop.open_for_write() as handle:
        renewed = FacilityRepository(handle.connection).renew(rin, until)
    click.echo(f"{renewed.rin} approved to {renewed.approved_until}")


@click.group()
def tech() -> None:
    """The people on the bench."""


@tech.command("add")
@click.argument("badge")
@click.argument("name")
@click.option("--methods", required=True, help="comma separated methods they are signed off for")
@click.option("--from", "qualified_from", default=None, help="the day they were signed off")
@click.option("--until", "qualified_until", default=None, help="the day it lapses, if it does")
@pass_shop
def add_technician(
    shop: ShopContext,
    badge: str,
    name: str,
    methods: str,
    qualified_from: str | None,
    qualified_until: str | None,
) -> None:
    """Sign somebody off."""
    record = Technician(
        badge=normalise_badge(badge),
        name=name,
        methods=parse_methods(methods),
        qualified_from=resolve_day(qualified_from, shop),
        qualified_until=None if qualified_until is None else parse_day(qualified_until),
    )
    with shop.open_for_write() as handle:
        TechnicianRepository(handle.connection).add(record)
    click.echo(f"signed off {record}")


@tech.command("list")
@pass_shop
def list_technicians(shop: ShopContext) -> None:
    """Who is on the bench and what they hold."""
    with shop.open() as handle:
        found = TechnicianRepository(handle.connection).all()
    if not found:
        click.echo("nobody on the bench")
        return
    click.echo(
        render_table(
            ["badge", "name", "from", "until", "methods"],
            [
                [
                    item.badge,
                    item.name,
                    item.qualified_from.isoformat(),
                    dash(item.qualified_until),
                    ", ".join(sorted(method.value for method in item.methods)),
                ]
                for item in found
            ],
        )
    )


@click.group()
def rig() -> None:
    """Test systems, their certificates and their daily checks."""


@rig.command("certify")
@click.argument("system_code")
@click.argument("instrument")
@click.option("--serial", required=True, help="the instrument's serial number")
@click.option("--issued", required=True, help="the day the certificate was issued")
@click.option("--until", "valid_until", required=True, help="the day it expires")
@click.option("--by", "issued_by", required=True, help="the calibration house")
@click.option("--standard", default="NIST traceable", show_default=True)
@pass_shop
def certify(
    shop: ShopContext,
    system_code: str,
    instrument: str,
    serial: str,
    issued: str,
    valid_until: str,
    issued_by: str,
    standard: str,
) -> None:
    """File a calibration certificate."""
    certificate = Certificate(
        system_code=normalise_system_code(system_code),
        instrument=InstrumentKind.parse(instrument),
        serial=serial,
        issued_on=parse_day(issued),
        valid_until=parse_day(valid_until),
        issued_by=issued_by,
        standard=standard,
    )
    with shop.open_for_write() as handle:
        CalibrationRepository(handle.connection).add_certificate(certificate)
    click.echo(f"filed {certificate}")


@rig.command("check")
@click.argument("system_code")
@click.argument("expected")
@click.argument("observed")
@click.option("--on", "day", default=None, help="the day of the check")
@click.option("--tech", default=None, help="who ran it")
@pass_shop
def daily_check(
    shop: ShopContext,
    system_code: str,
    expected: str,
    observed: str,
    day: str | None,
    tech: str | None,
) -> None:
    """Record the start of day run of the calibrated cylinder."""
    check = SystemCheck(
        system_code=normalise_system_code(system_code),
        day=resolve_day(day, shop),
        expected=Expansion.parse(expected),
        observed=Expansion.parse(observed),
        technician_badge=None if tech is None else normalise_badge(tech),
    )
    with shop.open_for_write() as handle:
        CalibrationRepository(handle.connection).record_check(check)
    verdict = "within tolerance" if check.within_tolerance else "OUT OF TOLERANCE"
    click.echo(f"{check.describe()}, {verdict}")


@rig.command("status")
@click.argument("system_code")
@click.option("--on", "day", default=None, help="the day to read it for")
@pass_shop
def rig_status(shop: ShopContext, system_code: str, day: str | None) -> None:
    """Say whether a rig was fit to test on a day."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        repository = CalibrationRepository(handle.connection)
        certificates = repository.certificates(system_code)
        check = repository.check_on(system_code, when)
    rows = [
        [
            certificate.instrument,
            certificate.serial,
            certificate.valid_until.isoformat(),
            yes_no(certificate.valid_on(when)),
        ]
        for certificate in certificates
    ]
    if rows:
        click.echo(render_table(["instrument", "serial", "expires", "in date"], rows))
    else:
        click.echo(f"no certificates on file for {system_code}")
    if check is None:
        click.echo(f"no start of day check for {when.isoformat()}")
    else:
        verdict = "within tolerance" if check.within_tolerance else "OUT OF TOLERANCE"
        click.echo(f"{check.describe()}, {verdict}")
