"""The statement an account gets at the end of the month.

It is three things on one page: what was invoiced, what is still owed and how
old it is, and what the shop actually did for the money. The third part is the
one customers ask for and the one an invoice on its own never answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.event import Outcome
from starstamp.model.invoice import Invoice
from starstamp.model.money import Money, total
from starstamp.reporting.aging import AccountAging, bucket_for
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.invoices import InvoiceRepository
from starstamp.store.owners import OwnerRepository
from starstamp.text.table import render_pairs, render_table


@dataclass(frozen=True)
class Statement:
    """One account, one window."""

    owner_code: str
    owner_name: str
    first: date
    last: date
    raised: tuple[Invoice, ...]
    settled: tuple[Invoice, ...]
    outstanding: tuple[Invoice, ...]
    requalified: int
    condemned: int
    day: date

    @property
    def invoiced(self) -> Money:
        return total([invoice.total for invoice in self.raised])

    @property
    def paid(self) -> Money:
        return total([invoice.total for invoice in self.settled])

    @property
    def owed(self) -> Money:
        return total([invoice.total for invoice in self.outstanding])

    def aging(self) -> AccountAging:
        return AccountAging(self.owner_code, self.outstanding, self.day)

    def oldest_bucket(self) -> str:
        if not self.outstanding:
            return "current"
        return bucket_for(max(item.days_overdue(self.day) for item in self.outstanding))

    def describe(self) -> str:
        return (
            f"{self.owner_code} {self.owner_name}, {self.first} to {self.last}: "
            f"{self.invoiced.with_symbol()} invoiced, {self.paid.with_symbol()} paid, "
            f"{self.owed.with_symbol()} outstanding"
        )


def build(book: Book, owner_code: str, first: date, last: date, day: date) -> Statement:
    owners = OwnerRepository(book.connection)
    invoices = InvoiceRepository(book.connection)
    events = EventRepository(book.connection)

    owner = owners.by_code(owner_code)
    every = invoices.for_owner(owner.code)
    raised = tuple(item for item in every if first <= item.raised_on <= last)
    settled = tuple(
        item for item in every if item.settled_on is not None and first <= item.settled_on <= last
    )
    outstanding = tuple(item for item in every if not item.is_settled)

    work = [
        event for event in events.for_owner_between(owner.code, first, last) if event.state.stands
    ]
    return Statement(
        owner_code=owner.code,
        owner_name=owner.name,
        first=first,
        last=last,
        raised=raised,
        settled=settled,
        outstanding=outstanding,
        requalified=sum(1 for event in work if event.outcome is Outcome.PASS),
        condemned=sum(1 for event in work if event.outcome is Outcome.CONDEMN),
        day=day,
    )


def render(statement: Statement) -> str:
    lines = [
        render_pairs(
            [
                ("account", f"{statement.owner_code} {statement.owner_name}"),
                ("period", f"{statement.first} to {statement.last}"),
                ("invoiced", statement.invoiced.with_symbol()),
                ("paid", statement.paid.with_symbol()),
                ("outstanding", statement.owed.with_symbol()),
                ("oldest", statement.oldest_bucket()),
                ("requalified", str(statement.requalified)),
                ("condemned", str(statement.condemned)),
            ]
        )
    ]
    if statement.raised:
        lines.append("")
        lines.append(
            render_table(
                ["invoice", "raised", "due", "amount", "settled"],
                [
                    [
                        invoice.number,
                        invoice.raised_on.isoformat(),
                        invoice.due_on.isoformat(),
                        str(invoice.total),
                        "-" if invoice.settled_on is None else invoice.settled_on.isoformat(),
                    ]
                    for invoice in statement.raised
                ],
                right=(3,),
            )
        )
    if statement.outstanding:
        lines.append("")
        buckets = statement.aging().buckets()
        lines.append(
            render_table(
                ["bucket", "amount"],
                [[label, str(amount)] for label, amount in buckets.items() if amount.cents],
                right=(1,),
            )
        )
    return "\n".join(lines)
