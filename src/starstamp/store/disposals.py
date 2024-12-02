"""Reading and writing disposals."""

from __future__ import annotations

import sqlite3
from datetime import date

from starstamp.errors import ConflictError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.disposal import Disposal, DisposalMethod
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_text,
    as_text,
    day_text,
)


def row_to_disposal(row: sqlite3.Row) -> Disposal:
    return Disposal(
        cylinder_key=as_text(row["cylinder_key"]),
        method=DisposalMethod(as_text(row["method"])),
        performed_on=as_day(row["performed_on"]),
        condemned_on=as_day(row["condemned_on"]),
        technician_badge=as_text(row["technician_badge"]),
        witness_badge=as_optional_text(row["witness_badge"]),
        scrap_ticket=as_optional_text(row["scrap_ticket"]),
        returned_to_owner=bool(as_int(row["returned_to_owner"])),
        note=as_optional_text(row["note"]),
        disposal_id=as_int(row["id"]),
    )


class DisposalRepository(Repository):
    _SELECT = (
        "SELECT d.*, c.manufacturer_symbol || '/' || c.serial AS cylinder_key FROM disposal d"
        " JOIN cylinder c ON c.id = d.cylinder_id"
    )

    def add(self, disposal: Disposal, cylinder_id: int, event_id: int | None) -> Disposal:
        try:
            cursor = self.connection.execute(
                "INSERT INTO disposal (cylinder_id, requalification_id, method, performed_on,"
                " condemned_on, technician_badge, witness_badge, scrap_ticket,"
                " returned_to_owner, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cylinder_id,
                    event_id,
                    disposal.method.value,
                    day_text(disposal.performed_on),
                    day_text(disposal.condemned_on),
                    disposal.technician_badge,
                    disposal.witness_badge,
                    disposal.scrap_ticket,
                    int(disposal.returned_to_owner),
                    disposal.note,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"{disposal.cylinder_key} has already been dealt with") from exc
        return self.by_id(int(cursor.lastrowid or 0))

    def by_id(self, disposal_id: int) -> Disposal:
        return row_to_disposal(
            self._one(
                f"{self._SELECT} WHERE d.id = ?", (disposal_id,), f"no disposal {disposal_id}"
            )
        )

    def for_cylinder(self, key: CylinderKey) -> Disposal | None:
        row = self.connection.execute(
            f"{self._SELECT} WHERE c.manufacturer_symbol = ? AND c.serial = ?",
            (key.manufacturer_symbol, key.serial),
        ).fetchone()
        return None if row is None else row_to_disposal(row)

    def between(self, first: date, last: date) -> list[Disposal]:
        rows = self._all(
            f"{self._SELECT} WHERE d.performed_on BETWEEN ? AND ? ORDER BY d.performed_on, d.id",
            (day_text(first), day_text(last)),
        )
        return [row_to_disposal(row) for row in rows]

    def held_for_owners(self) -> list[Disposal]:
        rows = self._all(
            f"{self._SELECT} WHERE d.method = ? ORDER BY d.condemned_on",
            (DisposalMethod.HELD_FOR_OWNER.value,),
        )
        return [row_to_disposal(row) for row in rows]

    def count(self) -> int:
        return self._count("SELECT count(*) FROM disposal")
