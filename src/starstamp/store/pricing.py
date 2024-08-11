"""Reading and writing the price book."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from starstamp.errors import ConflictError
from starstamp.model.money import Money
from starstamp.model.pricing import PriceBook, PriceItem, normalise_charge_code
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_day,
    as_text,
    day_text,
    optional_day_text,
)


def row_to_item(row: sqlite3.Row) -> PriceItem:
    return PriceItem(
        code=as_text(row["code"]),
        description=as_text(row["description"]),
        amount=Money(as_int(row["cents"])),
        effective_from=as_day(row["effective_from"]),
        effective_until=as_optional_day(row["effective_until"]),
    )


class PriceRepository(Repository):
    def add(self, item: PriceItem) -> int:
        try:
            cursor = self.connection.execute(
                "INSERT INTO price_item (code, description, cents, effective_from,"
                " effective_until) VALUES (?, ?, ?, ?, ?)",
                (
                    item.code,
                    item.description,
                    item.amount.cents,
                    day_text(item.effective_from),
                    optional_day_text(item.effective_until),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(
                f"{item.code} already has a price starting {item.effective_from}"
            ) from exc
        return int(cursor.lastrowid or 0)

    def raise_price(self, code: str, amount: Money, day: date, description: str) -> PriceItem:
        """Close whatever is open for a code and open a new price from a day.

        This is the only way a price changes. Editing the open row would make
        every invoice already raised against it unexplainable.
        """
        wanted = normalise_charge_code(code)
        self.connection.execute(
            "UPDATE price_item SET effective_until = ?"
            " WHERE code = ? AND effective_until IS NULL AND effective_from < ?",
            (day_text(day - timedelta(days=1)), wanted, day_text(day)),
        )
        item = PriceItem(code=wanted, description=description, amount=amount, effective_from=day)
        self.add(item)
        return item

    def book(self) -> PriceBook:
        rows = self._all("SELECT * FROM price_item ORDER BY code, effective_from")
        return PriceBook(tuple(row_to_item(row) for row in rows))

    def for_code(self, code: str) -> list[PriceItem]:
        rows = self._all(
            "SELECT * FROM price_item WHERE code = ? ORDER BY effective_from",
            (normalise_charge_code(code),),
        )
        return [row_to_item(row) for row in rows]

    def current(self, day: date) -> list[PriceItem]:
        return [item for item in self.book().items if item.applies_on(day)]
