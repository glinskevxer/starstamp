"""Reading and writing re-markings."""

from __future__ import annotations

import sqlite3
from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.marking import Evidence, MarkKind, Remarking, RestoredMark
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_text,
    as_text,
    day_text,
)


def row_to_remarking(row: sqlite3.Row, marks: tuple[RestoredMark, ...]) -> Remarking:
    return Remarking(
        cylinder_key=as_text(row["cylinder_key"]),
        marked_on=as_day(row["marked_on"]),
        facility_rin=as_text(row["facility_rin"]),
        technician_badge=as_text(row["technician_badge"]),
        evidence=Evidence(as_text(row["evidence"])),
        marks=marks,
        note=as_optional_text(row["note"]),
        remarking_id=as_int(row["id"]),
    )


class RemarkingRepository(Repository):
    _SELECT = (
        "SELECT r.*, c.manufacturer_symbol || '/' || c.serial AS cylinder_key FROM remarking r"
        " JOIN cylinder c ON c.id = r.cylinder_id"
    )

    def add(self, remarking: Remarking, cylinder_id: int) -> Remarking:
        cursor = self.connection.execute(
            "INSERT INTO remarking (cylinder_id, marked_on, facility_rin, technician_badge,"
            " evidence, note) VALUES (?, ?, ?, ?, ?, ?)",
            (
                cylinder_id,
                day_text(remarking.marked_on),
                remarking.facility_rin,
                remarking.technician_badge,
                remarking.evidence.value,
                remarking.note,
            ),
        )
        remarking_id = int(cursor.lastrowid or 0)
        for mark in remarking.marks:
            self.connection.execute(
                "INSERT INTO remarking_mark (remarking_id, kind, reads) VALUES (?, ?, ?)",
                (remarking_id, mark.kind.value, mark.reads),
            )
        return self.by_id(remarking_id)

    def marks_for(self, remarking_id: int) -> tuple[RestoredMark, ...]:
        rows = self._all(
            "SELECT * FROM remarking_mark WHERE remarking_id = ? ORDER BY id",
            (remarking_id,),
        )
        return tuple(
            RestoredMark(MarkKind(as_text(row["kind"])), as_text(row["reads"])) for row in rows
        )

    def by_id(self, remarking_id: int) -> Remarking:
        row = self._one(
            f"{self._SELECT} WHERE r.id = ?", (remarking_id,), f"no re-marking {remarking_id}"
        )
        return row_to_remarking(row, self.marks_for(remarking_id))

    def for_cylinder(self, key: CylinderKey) -> list[Remarking]:
        rows = self._all(
            f"{self._SELECT} WHERE c.manufacturer_symbol = ? AND c.serial = ?"
            " ORDER BY r.marked_on, r.id",
            (key.manufacturer_symbol, key.serial),
        )
        return [row_to_remarking(row, self.marks_for(as_int(row["id"]))) for row in rows]

    def between(self, first: date, last: date) -> list[Remarking]:
        rows = self._all(
            f"{self._SELECT} WHERE r.marked_on BETWEEN ? AND ? ORDER BY r.marked_on, r.id",
            (day_text(first), day_text(last)),
        )
        return [row_to_remarking(row, self.marks_for(as_int(row["id"]))) for row in rows]

    def count(self) -> int:
        return self._count("SELECT count(*) FROM remarking")
