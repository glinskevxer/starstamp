"""Requalification commands: the ones the bench actually types."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.errors import ValidationError
from starstamp.model.acetylene import AcetyleneExam
from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind, Observation, parse_thousandths
from starstamp.model.method import Method
from starstamp.model.testrecord import PressureReadings
from starstamp.model.ultrasonic import Position, Reading, Scan
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


def parse_scan(text: str) -> Scan:
    """Read a scan sheet off the command line: M1:0.215,M2:0.214.

    The thickness is in inches because that is what the meter reads out, and
    the position is the same label the paper scan sheet uses.
    """
    readings: list[Reading] = []
    for item in text.split(","):
        cleaned = item.strip()
        if not cleaned:
            continue
        position, _, thickness = cleaned.partition(":")
        if not thickness:
            raise ValidationError(f"a scan point is POSITION:INCHES, got {cleaned!r}")
        readings.append(Reading(Position.parse(position), parse_thousandths(thickness)))
    if not readings:
        raise ValidationError("a scan with no points in it is not a scan")
    return Scan(tuple(readings))


def build_acetylene(
    tare: str | None,
    plugs_bad: bool,
    mass_settled: bool,
    shell_bad: bool,
    cap_bad: bool,
) -> AcetyleneExam | None:
    """Build the weighing, or nothing at all if the cylinder was not weighed.

    The findings only mean something beside a weight, so a run that flags bad
    plugs without putting the cylinder on the scale is a refusal rather than a
    half filled record.
    """
    if tare is None:
        if plugs_bad or mass_settled or shell_bad or cap_bad:
            raise ValidationError("an acetylene finding needs the cylinder weighed; pass --tare")
        return None
    return AcetyleneExam(
        tare_now_hundredths_lb=parse_pounds(tare),
        fuse_plugs_sound=not plugs_bad,
        mass_settled=mass_settled,
        shell_sound=not shell_bad,
        cap_sound=not cap_bad,
    )


def parse_pounds(text: str) -> int:
    """Read a weight in pounds into hundredths."""
    cleaned = text.strip().lower().removesuffix("lb").strip()
    whole, _, part = cleaned.partition(".")
    if not whole.isdigit() or (part and not part.isdigit()) or len(part) > 2:
        raise ValidationError(f"a weight is pounds to two places, got {text!r}")
    return int(whole) * 100 + int(part.ljust(2, "0") or "0")


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
@click.option(
    "--scan",
    "scan_text",
    default=None,
    help="ultrasonic readings, M1:0.215,M2:0.214 and so on",
)
@click.option("--tare", default=None, help="the weight on the scale now, in pounds")
@click.option("--plugs-bad", is_flag=True, help="the fusible plugs are unsound")
@click.option("--mass-settled", is_flag=True, help="the porous mass has settled")
@click.option("--shell-bad", is_flag=True, help="the shell is unsound")
@click.option("--cap-bad", is_flag=True, help="the cap is unsound")
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
    scan_text: str | None,
    tare: str | None,
    plugs_bad: bool,
    mass_settled: bool,
    shell_bad: bool,
    cap_bad: bool,
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
        scan=None if scan_text is None else parse_scan(scan_text),
        acetylene=build_acetylene(tare, plugs_bad, mass_settled, shell_bad, cap_bad),
        facility_rin=rin,
    )
    with shop.open_for_write() as handle:
        result = RequalificationService(handle).perform(request)
    click.echo(result.summary())
    for reason in result.event.reasons:
        click.echo(f"  {reason}")
    if result.scan is not None:
        for note in result.scan.watch:
            click.echo(f"  watch: {note}")
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
        scan = repository.scan_for(event_id)
        weighing = repository.acetylene_exam(event_id)
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
    if scan.count:
        click.echo(f"  scan: {scan.describe()}")
        click.echo(
            "  "
            + render_table(
                ["point", "inches"],
                [
                    [str(reading.position), f"{reading.thousandths_in / 1000:.3f}"]
                    for reading in sorted(scan.readings, key=lambda item: item.position)
                ],
                right=(1,),
            ).replace("\n", "\n  ")
        )
    if weighing is not None:
        click.echo(f"  weighing: {weighing.describe()}")
    for reason in event.reasons:
        click.echo(f"  {reason}")
