"""Reading and writing receiving lots."""

from __future__ import annotations

import sqlite3
from datetime import date

from starstamp.errors import ConflictError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.lot import Lot, LotLine, LotStatus, format_lot_number, parse_lot_number
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_day,
    as_optional_int,
    as_optional_text,
    as_text,
    day_text,
    optional_day_text,
)


def row_to_lot(row: sqlite3.Row, owner_code: str) -> Lot:
    return Lot(
        number=as_text(row["number"]),
        owner_code=owner_code,
        received_on=as_day(row["received_on"]),
        promised_on=as_optional_day(row["promised_on"]),
        status=LotStatus(as_text(row["status"])),
        carrier=as_optional_text(row["carrier"]),
        note=as_optional_text(row["note"]),
        returned_on=as_optional_day(row["returned_on"]),
    )


class LotRepository(Repository):
    _SELECT = (
        "SELECT l.*, o.code AS owner_code FROM lot l JOIN owner_account o ON o.id = l.owner_id"
    )

    def next_number(self, year: int) -> str:
        """The next lot number for a year, from what the book already holds."""
        rows = self._all("SELECT number FROM lot WHERE number LIKE ?", (f"L{year:04d}-%",))
        serials = [parse_lot_number(as_text(row["number"]))[1] for row in rows]
        return format_lot_number(year, max(serials, default=0) + 1)

    def add(self, lot: Lot, owner_id: int) -> int:
        try:
            cursor = self.connection.execute(
                "INSERT INTO lot (number, owner_id, received_on, promised_on, status, carrier,"
                " note, returned_on) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    lot.number,
                    owner_id,
                    day_text(lot.received_on),
                    optional_day_text(lot.promised_on),
                    lot.status.value,
                    lot.carrier,
                    lot.note,
                    optional_day_text(lot.returned_on),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"lot {lot.number} is already open") from exc
        return int(cursor.lastrowid or 0)

    def by_number(self, number: str) -> Lot:
        wanted = number.strip().upper()
        row = self._one(f"{self._SELECT} WHERE l.number = ?", (wanted,), f"no lot {wanted}")
        return row_to_lot(row, as_text(row["owner_code"]))

    def id_of(self, number: str) -> int:
        wanted = number.strip().upper()
        row = self._one("SELECT id FROM lot WHERE number = ?", (wanted,), f"no lot {wanted}")
        return as_int(row["id"])

    def open_lots(self) -> list[Lot]:
        rows = self._all(
            f"{self._SELECT} WHERE l.status <> ? ORDER BY l.received_on, l.number",
            (LotStatus.RETURNED.value,),
        )
        return [row_to_lot(row, as_text(row["owner_code"])) for row in rows]

    def for_owner(self, owner_code: str) -> list[Lot]:
        rows = self._all(
            f"{self._SELECT} WHERE o.code = ? ORDER BY l.received_on, l.number",
            (owner_code.upper(),),
        )
        return [row_to_lot(row, owner_code.upper()) for row in rows]

    def received_between(self, first: date, last: date) -> list[Lot]:
        rows = self._all(
            f"{self._SELECT} WHERE l.received_on BETWEEN ? AND ? ORDER BY l.received_on",
            (day_text(first), day_text(last)),
        )
        return [row_to_lot(row, as_text(row["owner_code"])) for row in rows]

    def set_status(self, number: str, status: LotStatus, day: date | None = None) -> Lot:
        lot = self.by_number(number)
        if lot.status is LotStatus.RETURNED:
            raise ConflictError(f"{lot.number} went back on {lot.returned_on}")
        returned = day_text(day) if status is LotStatus.RETURNED and day else None
        if status is LotStatus.RETURNED and returned is None:
            raise ConflictError("a lot going back needs the day it went")
        self.connection.execute(
            "UPDATE lot SET status = ?, returned_on = ? WHERE number = ?",
            (status.value, returned, lot.number),
        )
        return self.by_number(number)

    def add_line(self, number: str, cylinder_id: int, key: CylinderKey, added_on: date) -> LotLine:
        lot = self.by_number(number)
        if not lot.status.accepts_work:
            raise ConflictError(f"{lot.number} is {lot.status.value} and takes no more cylinders")
        try:
            self.connection.execute(
                "INSERT INTO lot_line (lot_id, cylinder_id, added_on) VALUES (?, ?, ?)",
                (self.id_of(number), cylinder_id, day_text(added_on)),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"{key} is already on {lot.number}") from exc
        return LotLine(lot_number=lot.number, cylinder_key=str(key), added_on=added_on)

    def lines(self, number: str) -> list[LotLine]:
        rows = self._all(
            "SELECT ll.*, c.manufacturer_symbol AS symbol, c.serial AS serial FROM lot_line ll"
            " JOIN cylinder c ON c.id = ll.cylinder_id JOIN lot l ON l.id = ll.lot_id"
            " WHERE l.number = ? ORDER BY ll.id",
            (number.strip().upper(),),
        )
        return [
            LotLine(
                lot_number=number.strip().upper(),
                cylinder_key=f"{as_text(row['symbol'])}/{as_text(row['serial'])}",
                added_on=as_day(row["added_on"]),
                disposition=as_optional_text(row["disposition"]),
                event_id=as_optional_int(row["requalification_id"]),
            )
            for row in rows
        ]

    def settle(self, number: str, cylinder_id: int, disposition: str, event_id: int | None) -> None:
        """Write what became of one cylinder on a lot."""
        try:
            cursor = self.connection.execute(
                "UPDATE lot_line SET disposition = ?, requalification_id = ?"
                " WHERE lot_id = ? AND cylinder_id = ?",
                (disposition, event_id, self.id_of(number), cylinder_id),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"record of test {event_id} is not in this book") from exc
        if cursor.rowcount == 0:
            raise ConflictError(f"that cylinder is not on {number.strip().upper()}")

    def open_lines(self, number: str) -> list[LotLine]:
        return [line for line in self.lines(number) if not line.is_settled]

    def lots_holding(self, cylinder_id: int) -> list[str]:
        rows = self._all(
            "SELECT l.number FROM lot_line ll JOIN lot l ON l.id = ll.lot_id"
            " WHERE ll.cylinder_id = ? ORDER BY l.received_on",
            (cylinder_id,),
        )
        return [as_text(row["number"]) for row in rows]
