"""Commands that read the book and say whether it hangs together."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.model.cylinder import CylinderStatus
from starstamp.service.integrity import IntegrityService
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.events import EventRepository
from starstamp.store.invoices import InvoiceRepository
from starstamp.store.lots import LotRepository
from starstamp.store.migrations import schema_version
from starstamp.store.notices import NoticeRepository
from starstamp.text.table import render_pairs, render_table


@click.command("check")
@click.option("--on", "day", default=None, help="the day to read it as of")
@click.option("--warnings-are-fine", is_flag=True, help="exit zero when only warnings are found")
@pass_shop
def check(shop: ShopContext, day: str | None, warnings_are_fine: bool) -> None:
    """Look for things in the book that cannot all be true."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        report = IntegrityService(handle).run(when)
    click.echo(report.describe())
    if report.problems:
        raise SystemExit(7)
    if report.findings and not warnings_are_fine:
        raise SystemExit(8)


@click.command("stats")
@pass_shop
def stats(shop: ShopContext) -> None:
    """Count what is in the book."""
    with shop.open() as handle:
        cylinders = CylinderRepository(handle.connection)
        events = EventRepository(handle.connection)
        counts = {status.value: len(cylinders.with_status(status)) for status in CylinderStatus}
        click.echo(
            render_pairs(
                [
                    ("book", str(shop.book_path)),
                    ("schema", str(schema_version(handle.connection))),
                    ("cylinders", str(cylinders.count())),
                    ("records of test", str(events.count())),
                    ("lots open", str(len(LotRepository(handle.connection).open_lots()))),
                    ("notices unsent", str(len(NoticeRepository(handle.connection).unsent()))),
                    (
                        "invoices unpaid",
                        str(len(InvoiceRepository(handle.connection).outstanding())),
                    ),
                    ("test systems", str(len(CalibrationRepository(handle.connection).systems()))),
                ]
            )
        )
        click.echo("")
        click.echo(
            render_table(
                ["status", "cylinders"],
                [[status, str(count)] for status, count in counts.items() if count],
                right=(1,),
            )
        )
