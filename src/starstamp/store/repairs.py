"""Reading and writing repairs."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime

from starstamp.model.cylinder import CylinderKey
from starstamp.model.repair import Repair, RepairKind
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_int,
    as_optional_text,
    as_text,
    day_text,
)


def row_to_repair(row: sqlite3.Row, key: CylinderKey) -> Repair:
    return Repair(
        cylinder_key=str(key),
        kind=RepairKind(as_text(row["kind"])),
        performed_on=as_day(row["performed_on"]),
        technician_badge=as_text(row["technician_badge"]),
        facility_rin=as_optional_text(row["facility_rin"]),
        note=as_optional_text(row["note"]),
        parts=as_optional_text(row["parts"]),
        repair_id=as_int(row["id"]),
    )


class RepairRepository(Repository):
    _SELECT = (
        "SELECT r.*, c.manufacturer_symbol AS symbol, c.serial AS serial FROM repair r"
        " JOIN cylinder c ON c.id = r.cylinder_id"
    )

    def add(self, repair: Repair, cylinder_id: int, clears_event_id: int | None = None) -> Repair:
        cursor = self.connection.execute(
            "INSERT INTO repair (cylinder_id, kind, performed_on, technician_badge,"
            " facility_rin, parts, note, clears_event_id, recorded_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cylinder_id,
                repair.kind.value,
                day_text(repair.performed_on),
                repair.technician_badge,
                repair.facility_rin,
                repair.parts,
                repair.note,
                clears_event_id,
                datetime.now(tz=UTC).isoformat(timespec="seconds"),
            ),
        )
        from dataclasses import replace

        return replace(repair, repair_id=int(cursor.lastrowid or 0))

    def by_id(self, repair_id: int) -> Repair:
        row = self._one(f"{self._SELECT} WHERE r.id = ?", (repair_id,), f"no repair {repair_id}")
        return row_to_repair(row, CylinderKey(as_text(row["symbol"]), as_text(row["serial"])))

    def for_cylinder(self, key: CylinderKey) -> list[Repair]:
        rows = self._all(
            f"{self._SELECT} WHERE c.manufacturer_symbol = ? AND c.serial = ?"
            " ORDER BY r.performed_on, r.id",
            (key.manufacturer_symbol, key.serial),
        )
        return [row_to_repair(row, key) for row in rows]

    def between(self, first: date, last: date) -> list[Repair]:
        rows = self._all(
            f"{self._SELECT} WHERE r.performed_on BETWEEN ? AND ? ORDER BY r.performed_on, r.id",
            (day_text(first), day_text(last)),
        )
        return [
            row_to_repair(row, CylinderKey(as_text(row["symbol"]), as_text(row["serial"])))
            for row in rows
        ]

    def of_kind(self, kind: RepairKind) -> list[Repair]:
        rows = self._all(
            f"{self._SELECT} WHERE r.kind = ? ORDER BY r.performed_on, r.id", (kind.value,)
        )
        return [
            row_to_repair(row, CylinderKey(as_text(row["symbol"]), as_text(row["serial"])))
            for row in rows
        ]

    def clearing(self, event_id: int) -> list[Repair]:
        """The repairs booked against one suspended record of test."""
        rows = self._all(
            f"{self._SELECT} WHERE r.clears_event_id = ? ORDER BY r.performed_on, r.id",
            (event_id,),
        )
        return [
            row_to_repair(row, CylinderKey(as_text(row["symbol"]), as_text(row["serial"])))
            for row in rows
        ]

    def cleared_event_id(self, repair_id: int) -> int | None:
        row = self._one(
            "SELECT clears_event_id FROM repair WHERE id = ?",
            (repair_id,),
            f"no repair {repair_id}",
        )
        return as_optional_int(row["clears_event_id"])

    def count(self) -> int:
        return self._count("SELECT count(*) FROM repair")
