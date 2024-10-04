"""Comma separated output, for the people who want it in a spreadsheet.

Every export is flat and every one of them carries the keys somebody would
need to join it back to the others: the cylinder, the record of test, the day.
Nothing is rounded on the way out. Expansions leave in cc with one decimal
because that is how they were read, and money leaves in dollars and cents
rather than in cents, because a spreadsheet will read it as a number either
way and only one of them means what it says.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date

from starstamp.model.event import RequalificationEvent
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.invoices import InvoiceRepository

CYLINDER_HEADERS = (
    "cylinder",
    "manufacturer",
    "serial",
    "specification",
    "service",
    "owner",
    "status",
    "manufactured",
    "ree_cc",
    "wall_in",
)

EVENT_HEADERS = (
    "record",
    "cylinder",
    "performed_on",
    "method",
    "outcome",
    "rin",
    "technician",
    "system",
    "applied_psig",
    "total_cc",
    "permanent_cc",
    "starred",
    "plus",
    "state",
    "reasons",
)

INVOICE_HEADERS = (
    "invoice",
    "owner",
    "raised_on",
    "due_on",
    "settled_on",
    "code",
    "performed_on",
    "cylinder",
    "count",
    "unit",
    "amount",
)


def to_csv(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    """Render rows as CSV with the line endings a spreadsheet expects."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def _expansion(value: object) -> str:
    if value is None:
        return ""
    return str(value).removesuffix(" cc")


def cylinder_rows(book: Book, owner_code: str | None = None) -> list[list[str]]:
    repository = CylinderRepository(book.connection)
    if owner_code is not None:
        fleet = repository.for_owner(owner_code.upper())
    else:
        from starstamp.model.cylinder import CylinderStatus

        fleet = [
            cylinder for status in CylinderStatus for cylinder in repository.with_status(status)
        ]
    return [
        [
            str(cylinder.key),
            cylinder.key.manufacturer_symbol,
            cylinder.key.serial,
            str(cylinder.specification),
            cylinder.service.code,
            cylinder.owner_code,
            cylinder.status.value,
            cylinder.manufactured.long_form(),
            _expansion(cylinder.rejection_elastic_expansion),
            ""
            if cylinder.nominal_wall_thousandths_in is None
            else f"{cylinder.nominal_wall_thousandths_in / 1000:.3f}",
        ]
        for cylinder in sorted(fleet, key=lambda item: item.key)
    ]


def event_rows(book: Book, first: date, last: date) -> list[list[str]]:
    events: list[RequalificationEvent] = EventRepository(book.connection).between(first, last)
    rows: list[list[str]] = []
    for event in events:
        readings = event.readings
        rows.append(
            [
                str(event.event_id or ""),
                str(event.cylinder),
                event.performed_on.isoformat(),
                event.method.value,
                event.outcome.value,
                event.facility_rin,
                event.technician_badge,
                event.system_code or "",
                "" if readings is None else str(readings.applied.psig),
                "" if readings is None else _expansion(readings.total_expansion),
                "" if readings is None else _expansion(readings.permanent_expansion),
                "yes" if event.starred else "no",
                "yes" if event.plus_rated else "no",
                event.state.value,
                "; ".join(event.reasons),
            ]
        )
    return rows


def invoice_rows(book: Book, owner_code: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for invoice in InvoiceRepository(book.connection).for_owner(owner_code):
        for line in invoice.lines:
            rows.append(
                [
                    invoice.number,
                    invoice.owner_code,
                    invoice.raised_on.isoformat(),
                    invoice.due_on.isoformat(),
                    "" if invoice.settled_on is None else invoice.settled_on.isoformat(),
                    line.code,
                    line.performed_on.isoformat(),
                    line.cylinder_key or "",
                    str(line.count),
                    str(line.unit),
                    str(line.amount),
                ]
            )
    return rows


def cylinders_csv(book: Book, owner_code: str | None = None) -> str:
    return to_csv(CYLINDER_HEADERS, cylinder_rows(book, owner_code))


def events_csv(book: Book, first: date, last: date) -> str:
    return to_csv(EVENT_HEADERS, event_rows(book, first, last))


def invoices_csv(book: Book, owner_code: str) -> str:
    return to_csv(INVOICE_HEADERS, invoice_rows(book, owner_code))
