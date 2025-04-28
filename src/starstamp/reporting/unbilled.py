"""Work the shop has done and not charged for.

This is the report that pays for itself. A requalification that never reaches
an invoice is not a rounding error: it is fourteen dollars and the customer's
goodwill, and the usual cause is a lot that was billed before the last cylinder
on it was finished.

It reads the same two things billing reads, in the same way, and then reports
the difference rather than acting on it. Nothing here writes an invoice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import NotFoundError
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.money import Money, total
from starstamp.model.pricing import code_for
from starstamp.store.contracts import ContractRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.invoices import InvoiceRepository
from starstamp.store.owners import OwnerRepository
from starstamp.store.pricing import PriceRepository
from starstamp.text.table import render_table


@dataclass(frozen=True)
class UnbilledEvent:
    """One record of test nobody has charged for."""

    event: RequalificationEvent
    owner_code: str
    value: Money

    def row(self, today: date) -> list[str]:
        return [
            self.event.performed_on.isoformat(),
            str(self.event.cylinder),
            self.owner_code,
            self.event.method.label,
            self.event.outcome.value,
            str(self.value),
            str((today - self.event.performed_on).days),
        ]


@dataclass(frozen=True)
class Unbilled:
    """Everything unbilled, by account."""

    day: date
    events: tuple[UnbilledEvent, ...]

    @property
    def value(self) -> Money:
        return total([item.value for item in self.events])

    def by_owner(self) -> dict[str, Money]:
        found: dict[str, Money] = {}
        for item in self.events:
            found[item.owner_code] = found.get(item.owner_code, Money.zero()).plus(item.value)
        return dict(sorted(found.items(), key=lambda pair: (-pair[1].cents, pair[0])))

    def oldest(self) -> UnbilledEvent | None:
        if not self.events:
            return None
        return min(self.events, key=lambda item: item.event.performed_on)

    def describe(self) -> str:
        if not self.events:
            return f"everything up to {self.day.isoformat()} has been billed"
        oldest = self.oldest()
        line = f"{len(self.events)} records worth {self.value.with_symbol()} unbilled"
        if oldest is not None:
            days = (self.day - oldest.event.performed_on).days
            line = f"{line}; the oldest is {days} days old"
        return line


def build(book: Book, day: date) -> Unbilled:
    events = EventRepository(book.connection)
    invoices = InvoiceRepository(book.connection)
    cylinders = CylinderRepository(book.connection)
    prices = PriceRepository(book.connection).book()
    contracts = ContractRepository(book.connection)
    owners = OwnerRepository(book.connection)

    billed: dict[str, set[int]] = {
        code: invoices.billed_event_ids(code) for code in _owner_codes(owners)
    }
    found: list[UnbilledEvent] = []
    for event in events.between(date(1900, 1, 1), day):
        if not event.state.stands or event.outcome not in {Outcome.PASS, Outcome.CONDEMN}:
            continue
        owner_code = cylinders.by_key(event.cylinder).owner_code
        if event.event_id is not None and event.event_id in billed.get(owner_code, set()):
            continue
        code = code_for(event.method)
        try:
            list_price = prices.amount(code, event.performed_on)
        except NotFoundError:
            list_price = Money.zero()
        value = contracts.contract(owner_code).price(code, event.performed_on, list_price)
        found.append(UnbilledEvent(event, owner_code, value))
    return Unbilled(day, tuple(found))


def _owner_codes(owners: OwnerRepository) -> list[str]:
    return [account.code for account in owners.all()]


def render(unbilled: Unbilled) -> str:
    lines = [unbilled.describe()]
    if not unbilled.events:
        return lines[0]
    lines.append("")
    lines.append(
        render_table(
            ["date", "cylinder", "owner", "method", "outcome", "value", "days"],
            [item.row(unbilled.day) for item in unbilled.events],
            right=(5, 6),
        )
    )
    lines.append("")
    lines.append(
        render_table(
            ["owner", "unbilled"],
            [[code, str(amount)] for code, amount in unbilled.by_owner().items()],
            right=(1,),
        )
    )
    return "\n".join(lines)
