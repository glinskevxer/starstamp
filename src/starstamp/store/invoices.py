"""Reading and writing invoices."""

from __future__ import annotations

import sqlite3
from datetime import date

from starstamp.errors import ConflictError
from starstamp.model.invoice import (
    Invoice,
    InvoiceLine,
    format_invoice_number,
    parse_invoice_number,
)
from starstamp.model.money import Money
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_day,
    as_optional_int,
    as_optional_text,
    as_text,
    day_text,
)


def row_to_line(row: sqlite3.Row) -> InvoiceLine:
    return InvoiceLine(
        code=as_text(row["code"]),
        description=as_text(row["description"]),
        performed_on=as_day(row["performed_on"]),
        unit=Money(as_int(row["unit_cents"])),
        count=as_int(row["count"]),
        cylinder_key=as_optional_text(row["cylinder_key"]),
        event_id=as_optional_int(row["requalification_id"]),
    )


class InvoiceRepository(Repository):
    _SELECT = (
        "SELECT i.*, o.code AS owner_code FROM invoice i JOIN owner_account o ON o.id = i.owner_id"
    )
    _LINES = (
        "SELECT il.*, c.manufacturer_symbol || '/' || c.serial AS cylinder_key"
        " FROM invoice_line il LEFT JOIN cylinder c ON c.id = il.cylinder_id"
        " WHERE il.invoice_id = ? ORDER BY il.id"
    )

    def next_number(self, year: int) -> str:
        rows = self._all("SELECT number FROM invoice WHERE number LIKE ?", (f"I{year:04d}-%",))
        serials = [parse_invoice_number(as_text(row["number"]))[1] for row in rows]
        return format_invoice_number(year, max(serials, default=0) + 1)

    def add(self, invoice: Invoice, owner_id: int, cylinder_ids: dict[str, int]) -> Invoice:
        try:
            cursor = self.connection.execute(
                "INSERT INTO invoice (number, owner_id, raised_on, due_on, first_day, last_day,"
                " total_cents) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    invoice.number,
                    owner_id,
                    day_text(invoice.raised_on),
                    day_text(invoice.due_on),
                    day_text(invoice.first_day),
                    day_text(invoice.last_day),
                    invoice.total.cents,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"invoice {invoice.number} was already raised") from exc
        invoice_id = int(cursor.lastrowid or 0)
        for line in invoice.lines:
            self.connection.execute(
                "INSERT INTO invoice_line (invoice_id, code, description, performed_on,"
                " cylinder_id, requalification_id, count, unit_cents, line_cents)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    invoice_id,
                    line.code,
                    line.description,
                    day_text(line.performed_on),
                    cylinder_ids.get(line.cylinder_key or ""),
                    line.event_id,
                    line.count,
                    line.unit.cents,
                    line.amount.cents,
                ),
            )
        return self.by_number(invoice.number)

    def by_number(self, number: str) -> Invoice:
        wanted = number.strip().upper()
        row = self._one(f"{self._SELECT} WHERE i.number = ?", (wanted,), f"no invoice {wanted}")
        lines = [row_to_line(item) for item in self._all(self._LINES, (as_int(row["id"]),))]
        return Invoice(
            number=as_text(row["number"]),
            owner_code=as_text(row["owner_code"]),
            raised_on=as_day(row["raised_on"]),
            due_on=as_day(row["due_on"]),
            first_day=as_day(row["first_day"]),
            last_day=as_day(row["last_day"]),
            lines=tuple(lines),
            settled_on=as_optional_day(row["settled_on"]),
        )

    def for_owner(self, owner_code: str) -> list[Invoice]:
        rows = self._all(
            f"{self._SELECT} WHERE o.code = ? ORDER BY i.raised_on, i.number",
            (owner_code.upper(),),
        )
        return [self.by_number(as_text(row["number"])) for row in rows]

    def outstanding(self) -> list[Invoice]:
        """Everything unpaid, the one that fell due first at the top."""
        rows = self._all(f"{self._SELECT} WHERE i.settled_on IS NULL ORDER BY i.due_on, i.number")
        return [self.by_number(as_text(row["number"])) for row in rows]

    def overdue(self, today: date) -> list[Invoice]:
        return [invoice for invoice in self.outstanding() if invoice.is_overdue(today)]

    def settle(self, number: str, day: date) -> Invoice:
        invoice = self.by_number(number)
        if invoice.is_settled:
            raise ConflictError(f"{invoice.number} was settled on {invoice.settled_on}")
        if day < invoice.raised_on:
            raise ConflictError(f"{invoice.number} was raised on {invoice.raised_on}")
        self.connection.execute(
            "UPDATE invoice SET settled_on = ? WHERE number = ?", (day_text(day), invoice.number)
        )
        return self.by_number(number)

    def billed_event_ids(self, owner_code: str) -> set[int]:
        """Every record of test already on an invoice for an account."""
        rows = self._all(
            "SELECT il.requalification_id AS id FROM invoice_line il"
            " JOIN invoice i ON i.id = il.invoice_id JOIN owner_account o ON o.id = i.owner_id"
            " WHERE o.code = ? AND il.requalification_id IS NOT NULL",
            (owner_code.upper(),),
        )
        return {as_int(row["id"]) for row in rows}
