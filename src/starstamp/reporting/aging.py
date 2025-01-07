"""Who owes what, and for how long.

The buckets are the ones every accounts department already reads: current,
then thirty, sixty and ninety days past due. What matters here is which date
the age is measured from. It is the due date, not the raised date, because an
account on forty five day terms is not late at thirty and an account on cash
terms is.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.invoice import Invoice
from starstamp.model.money import Money, total
from starstamp.store.db import Book
from starstamp.store.invoices import InvoiceRepository
from starstamp.text.table import render_table

BUCKETS = ((0, "current"), (30, "1 to 30"), (60, "31 to 60"), (90, "61 to 90"))
OLDEST = "over 90"


def bucket_for(days_overdue: int) -> str:
    """Which column an invoice falls in, by how far past due it is."""
    if days_overdue <= 0:
        return "current"
    for limit, label in BUCKETS[1:]:
        if days_overdue <= limit:
            return label
    return OLDEST


@dataclass(frozen=True)
class AccountAging:
    """One account's unpaid invoices, bucketed."""

    owner_code: str
    invoices: tuple[Invoice, ...]
    day: date

    @property
    def outstanding(self) -> Money:
        return total([invoice.total for invoice in self.invoices])

    def buckets(self) -> dict[str, Money]:
        found: dict[str, Money] = {label: Money.zero() for _, label in BUCKETS}
        found[OLDEST] = Money.zero()
        for invoice in self.invoices:
            label = bucket_for(invoice.days_overdue(self.day))
            found[label] = found[label].plus(invoice.total)
        return found

    @property
    def oldest_days(self) -> int:
        if not self.invoices:
            return 0
        return max(invoice.days_overdue(self.day) for invoice in self.invoices)

    def row(self) -> list[str]:
        buckets = self.buckets()
        return [
            self.owner_code,
            str(self.outstanding),
            *[str(buckets[label]) for _, label in BUCKETS],
            str(buckets[OLDEST]),
            str(self.oldest_days),
        ]


@dataclass(frozen=True)
class Aging:
    """Every account with something unpaid."""

    day: date
    accounts: tuple[AccountAging, ...]

    @property
    def outstanding(self) -> Money:
        return total([account.outstanding for account in self.accounts])

    def buckets(self) -> dict[str, Money]:
        found: dict[str, Money] = {label: Money.zero() for _, label in BUCKETS}
        found[OLDEST] = Money.zero()
        for account in self.accounts:
            for label, amount in account.buckets().items():
                found[label] = found[label].plus(amount)
        return found

    def worst(self) -> AccountAging | None:
        if not self.accounts:
            return None
        return max(self.accounts, key=lambda account: account.oldest_days)

    def describe(self) -> str:
        if not self.accounts:
            return f"nothing outstanding on {self.day.isoformat()}"
        buckets = self.buckets()
        return (
            f"{self.outstanding.with_symbol()} outstanding across {len(self.accounts)} "
            f"accounts, {buckets[OLDEST].with_symbol()} of it over ninety days"
        )


def build(book: Book, day: date) -> Aging:
    grouped: dict[str, list[Invoice]] = {}
    for invoice in InvoiceRepository(book.connection).outstanding():
        grouped.setdefault(invoice.owner_code, []).append(invoice)
    accounts = tuple(
        AccountAging(owner, tuple(invoices), day) for owner, invoices in sorted(grouped.items())
    )
    return Aging(day, accounts)


def render(aging: Aging) -> str:
    if not aging.accounts:
        return aging.describe()
    headers = ["account", "total", *[label for _, label in BUCKETS], OLDEST, "oldest"]
    table = render_table(
        headers,
        [account.row() for account in aging.accounts],
        right=tuple(range(1, len(headers))),
    )
    return f"{table}\n\n{aging.describe()}"
