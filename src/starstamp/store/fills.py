"""Reading and writing the fill log."""

from __future__ import annotations

import sqlite3
from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.fillrecord import FillRecord
from starstamp.model.service import lookup_service
from starstamp.model.units import Pressure
from starstamp.rules.filling import FillVerdict
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_int,
    as_optional_text,
    as_text,
    day_text,
)


def row_to_fill(row: sqlite3.Row) -> FillRecord:
    pressure = as_optional_int(row["pressure_psig"])
    return FillRecord(
        cylinder_key=as_text(row["cylinder_key"]),
        service=lookup_service(as_text(row["service_code"])),
        filled_on=as_day(row["filled_on"]),
        filler_badge=as_text(row["filler_badge"]),
        pressure=None if pressure is None else Pressure(pressure),
        weight_hundredths_lb=as_optional_int(row["weight_hundredths_lb"]),
        temperature_f=as_int(row["temperature_f"]),
        note=as_optional_text(row["note"]),
        fill_id=as_int(row["id"]),
    )


class FillRepository(Repository):
    _SELECT = (
        "SELECT f.*, c.manufacturer_symbol || '/' || c.serial AS cylinder_key FROM fill f"
        " JOIN cylinder c ON c.id = f.cylinder_id"
    )

    def add(
        self,
        record: FillRecord,
        cylinder_id: int,
        verdict: FillVerdict,
        settled: Pressure | None,
        ceiling: Pressure | None,
    ) -> FillRecord:
        cursor = self.connection.execute(
            "INSERT INTO fill (cylinder_id, service_code, filled_on, filler_badge,"
            " pressure_psig, weight_hundredths_lb, temperature_f, settled_psig, ceiling_psig,"
            " verdict, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cylinder_id,
                record.service.code,
                day_text(record.filled_on),
                record.filler_badge,
                None if record.pressure is None else record.pressure.psig,
                record.weight_hundredths_lb,
                record.temperature_f,
                None if settled is None else settled.psig,
                None if ceiling is None else ceiling.psig,
                verdict.value,
                record.note,
            ),
        )
        return self.by_id(int(cursor.lastrowid or 0))

    def by_id(self, fill_id: int) -> FillRecord:
        return row_to_fill(
            self._one(f"{self._SELECT} WHERE f.id = ?", (fill_id,), f"no fill {fill_id}")
        )

    def verdict_of(self, fill_id: int) -> FillVerdict:
        row = self._one("SELECT verdict FROM fill WHERE id = ?", (fill_id,), f"no fill {fill_id}")
        return FillVerdict(as_text(row["verdict"]))

    def for_cylinder(self, key: CylinderKey) -> list[FillRecord]:
        rows = self._all(
            f"{self._SELECT} WHERE c.manufacturer_symbol = ? AND c.serial = ?"
            " ORDER BY f.filled_on, f.id",
            (key.manufacturer_symbol, key.serial),
        )
        return [row_to_fill(row) for row in rows]

    def between(self, first: date, last: date) -> list[FillRecord]:
        rows = self._all(
            f"{self._SELECT} WHERE f.filled_on BETWEEN ? AND ? ORDER BY f.filled_on, f.id",
            (day_text(first), day_text(last)),
        )
        return [row_to_fill(row) for row in rows]

    def overfills(self, first: date, last: date) -> list[FillRecord]:
        """The fills that settled over the cylinder's ceiling."""
        rows = self._all(
            f"{self._SELECT} WHERE f.verdict = ? AND f.filled_on BETWEEN ? AND ?"
            " ORDER BY f.filled_on, f.id",
            (FillVerdict.OVERFILLED.value, day_text(first), day_text(last)),
        )
        return [row_to_fill(row) for row in rows]

    def last_fill(self, key: CylinderKey) -> FillRecord | None:
        found = self.for_cylinder(key)
        return found[-1] if found else None

    def count(self) -> int:
        return self._count("SELECT count(*) FROM fill")
