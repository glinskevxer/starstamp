"""The month end pack: everything the owner of the shop reads on one page.

Each piece of this already exists on its own. What is worth having here is the
combination, in the order somebody actually reads it: what came through, what
it earned, what is still owed, and what is coming. A shop that only reads the
throughput report knows it was busy and not whether it was paid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.dates import StampedMonth
from starstamp.model.invoice import Invoice
from starstamp.model.money import Money
from starstamp.reporting import aging, condemnation, forecast, throughput
from starstamp.reporting.throughput import Tally
from starstamp.store.db import Book
from starstamp.store.invoices import InvoiceRepository
from starstamp.text.table import render_pairs


@dataclass(frozen=True)
class Close:
    """One month, closed."""

    month: StampedMonth
    tally: Tally
    invoiced: Money
    settled: Money
    outstanding: Money
    over_ninety: Money
    condemned: condemnation.Analysis
    ahead: forecast.Forecast

    @property
    def worked(self) -> int:
        return self.tally.total

    @property
    def earned_per_cylinder(self) -> Money:
        if self.tally.decided == 0:
            return Money.zero()
        return self.invoiced.share_of(1, self.tally.decided)

    def describe(self) -> str:
        return (
            f"{self.month.long_form()}: {self.worked} cylinders, "
            f"{self.invoiced.with_symbol()} invoiced, "
            f"{self.outstanding.with_symbol()} outstanding"
        )


def build(book: Book, month: StampedMonth, today: date) -> Close:
    first, last = month.first_day(), month.last_day()
    events = throughput.standing_between(book, first, last)
    invoices = InvoiceRepository(book.connection)

    raised = [invoice for invoice in _every_invoice(invoices) if first <= invoice.raised_on <= last]
    settled = [
        invoice
        for invoice in _every_invoice(invoices)
        if invoice.settled_on is not None and first <= invoice.settled_on <= last
    ]
    ledger = aging.build(book, last)
    return Close(
        month=month,
        tally=throughput.overall(events),
        invoiced=Money(sum(invoice.total.cents for invoice in raised)),
        settled=Money(sum(invoice.total.cents for invoice in settled)),
        outstanding=ledger.outstanding,
        over_ninety=ledger.buckets()[aging.OLDEST],
        condemned=condemnation.build(book, first, last),
        ahead=forecast.build(book, today, 6),
    )


def _every_invoice(invoices: InvoiceRepository) -> list[Invoice]:
    """Every invoice in the book, which no repository method offers alone."""
    found: list[Invoice] = []
    for owner_code in invoices.accounts_invoiced():
        found.extend(invoices.for_owner(owner_code))
    return found


def render(pack: Close) -> str:
    lines = [
        render_pairs(
            [
                ("month", pack.month.long_form()),
                ("cylinders", str(pack.worked)),
                ("passed", str(pack.tally.passed)),
                ("condemned", str(pack.tally.condemned)),
                ("suspended", str(pack.tally.suspended)),
                ("condemn rate", f"{float(pack.tally.condemn_rate):.1f}%"),
                ("invoiced", pack.invoiced.with_symbol()),
                ("settled", pack.settled.with_symbol()),
                ("outstanding", pack.outstanding.with_symbol()),
                ("over ninety days", pack.over_ninety.with_symbol()),
                ("per cylinder", pack.earned_per_cylinder.with_symbol()),
            ]
        )
    ]
    if pack.condemned.count:
        lines.append("")
        lines.append(pack.condemned.describe())
    lines.append("")
    lines.append(pack.ahead.describe())
    return "\n".join(lines)
