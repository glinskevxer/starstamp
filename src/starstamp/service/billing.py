"""Turning a month's work into an invoice.

Two rules here are worth stating because both are easy to get wrong and both
show up as a customer query rather than as a bug.

A line is priced at the price in force on the day the work was done, not the
day the invoice was raised. And a record of test that has already been billed
is never billed again, even when a later invoice covers the same window: the
window decides what to look at, the billing history decides what to charge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import ConflictError
from starstamp.model.contract import Contract
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.invoice import Invoice, InvoiceLine, due_date
from starstamp.model.money import Money
from starstamp.model.pricing import CONDEMNATION, HANDLING, PriceBook, code_for
from starstamp.store.contracts import ContractRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.invoices import InvoiceRepository
from starstamp.store.lots import LotRepository
from starstamp.store.owners import OwnerRepository
from starstamp.store.pricing import PriceRepository

BILLABLE = {Outcome.PASS, Outcome.CONDEMN}


@dataclass(frozen=True)
class Draft:
    """An invoice that has not been raised, and what was left off it."""

    invoice: Invoice
    skipped: tuple[str, ...]

    @property
    def total(self) -> Money:
        return self.invoice.total

    @property
    def is_empty(self) -> bool:
        return not self.invoice.lines


class BillingService:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.events = EventRepository(book.connection)
        self.invoices = InvoiceRepository(book.connection)
        self.owners = OwnerRepository(book.connection)
        self.prices = PriceRepository(book.connection)
        self.contracts = ContractRepository(book.connection)
        self.lots = LotRepository(book.connection)
        self.cylinders = CylinderRepository(book.connection)

    def draft(
        self,
        owner_code: str,
        first: date,
        last: date,
        raised_on: date,
        *,
        number: str | None = None,
    ) -> Draft:
        """Work out what an account owes for a window without writing anything."""
        if last < first:
            raise ConflictError("an invoice window ends after it starts")
        owner = self.owners.by_code(owner_code)
        book = self.prices.book()
        contract = self.contracts.contract(owner.code)
        already = self.invoices.billed_event_ids(owner.code)

        lines: list[InvoiceLine] = []
        skipped: list[str] = []
        for event in self.events.for_owner_between(owner.code, first, last):
            reason = self._skip_reason(event, already)
            if reason is not None:
                skipped.append(f"{event.cylinder} {event.performed_on.isoformat()}: {reason}")
                continue
            lines.extend(self._lines_for(event, book, contract))

        for lot in self.lots.for_owner(owner.code):
            if first <= lot.received_on <= last:
                lines.append(
                    InvoiceLine(
                        code=HANDLING,
                        description=f"handling {lot.number}",
                        performed_on=lot.received_on,
                        unit=contract.price(
                            HANDLING,
                            lot.received_on,
                            book.amount(HANDLING, lot.received_on),
                        ),
                    )
                )

        invoice = Invoice(
            number=number or self.invoices.next_number(raised_on.year),
            owner_code=owner.code,
            raised_on=raised_on,
            due_on=due_date(raised_on, owner.terms_days),
            first_day=first,
            last_day=last,
            lines=tuple(lines),
        )
        return Draft(invoice, tuple(skipped))

    def raise_invoice(self, owner_code: str, first: date, last: date, raised_on: date) -> Invoice:
        """Draft it and write it, refusing an invoice with nothing on it."""
        draft = self.draft(owner_code, first, last, raised_on)
        if draft.is_empty:
            raise ConflictError(f"nothing to bill {owner_code.upper()} between {first} and {last}")
        keys = {
            line.cylinder_key: self.cylinders.id_of(self.cylinders.by_key_from(line.cylinder_key))
            for line in draft.invoice.lines
            if line.cylinder_key
        }
        return self.invoices.add(draft.invoice, self.owners.id_of(owner_code), keys)

    def _skip_reason(self, event: RequalificationEvent, already: set[int]) -> str | None:
        if not event.state.stands:
            return "the record was reversed"
        if event.outcome not in BILLABLE:
            return f"the cylinder was {event.outcome.value}"
        if event.event_id is not None and event.event_id in already:
            return "already billed"
        return None

    def _lines_for(
        self, event: RequalificationEvent, book: PriceBook, contract: Contract
    ) -> list[InvoiceLine]:
        """Price one record of test, at the account's price where it has one."""
        code = code_for(event.method)
        lines = [
            InvoiceLine(
                code=code,
                description=f"{event.method.label} requalification",
                performed_on=event.performed_on,
                unit=contract.price(
                    code, event.performed_on, book.amount(code, event.performed_on)
                ),
                cylinder_key=str(event.cylinder),
                event_id=event.event_id,
            )
        ]
        if event.outcome is Outcome.CONDEMN:
            lines.append(
                InvoiceLine(
                    code=CONDEMNATION,
                    description="condemnation and disposal",
                    performed_on=event.performed_on,
                    unit=contract.price(
                        CONDEMNATION,
                        event.performed_on,
                        book.amount(CONDEMNATION, event.performed_on),
                    ),
                    cylinder_key=str(event.cylinder),
                    event_id=event.event_id,
                )
            )
        return lines
