"""Reading and writing cylinders.

The row carries the marks as text and integers, and this module is the only
place that knows how to turn those back into the value objects. Nothing else
parses a spec code out of the database.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.cylinder import Cylinder, CylinderKey, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.service import GasService, lookup_service
from starstamp.model.specification import parse_specification
from starstamp.model.units import Expansion
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_int,
    as_optional_text,
    as_text,
    day_text,
)


def row_to_cylinder(row: sqlite3.Row, owner_code: str) -> Cylinder:
    ree = as_optional_int(row["ree_tenths_cc"])
    return Cylinder(
        key=CylinderKey(as_text(row["manufacturer_symbol"]), as_text(row["serial"])),
        specification=parse_specification(as_text(row["spec_marking"])),
        manufactured=StampedMonth(as_int(row["dom_year"]), as_int(row["dom_month"])),
        service=lookup_service(as_text(row["service_code"])),
        owner_code=owner_code,
        status=CylinderStatus(as_text(row["status"])),
        rejection_elastic_expansion=None if ree is None else Expansion(ree),
        water_capacity_tenths_l=as_optional_int(row["water_capacity_tenths_l"]),
        tare_hundredths_lb=as_optional_int(row["tare_hundredths_lb"]),
        nominal_wall_thousandths_in=as_optional_int(row["nominal_wall_thousandths_in"]),
        wall_source=as_optional_text(row["wall_source"]),
    )


class CylinderRepository(Repository):
    """Cylinders, joined to their owner on the way out."""

    _SELECT = (
        "SELECT c.*, o.code AS owner_code FROM cylinder c JOIN owner_account o ON o.id = c.owner_id"
    )

    def add(self, cylinder: Cylinder, owner_id: int, recorded_on: date) -> int:
        spec = cylinder.specification
        try:
            cursor = self.connection.execute(
                "INSERT INTO cylinder (serial, manufacturer_symbol, spec_code, spec_family,"
                " spec_marking, service_pressure_psig, permit_number, service_code, dom_year,"
                " dom_month, ree_tenths_cc, water_capacity_tenths_l, tare_hundredths_lb,"
                " nominal_wall_thousandths_in, wall_source, owner_id, status, recorded_on)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cylinder.key.serial,
                    cylinder.key.manufacturer_symbol,
                    spec.code,
                    spec.family.value,
                    str(spec),
                    None if spec.service_pressure is None else spec.service_pressure.psig,
                    spec.permit_number,
                    cylinder.service.code,
                    cylinder.manufactured.year,
                    cylinder.manufactured.month,
                    None
                    if cylinder.rejection_elastic_expansion is None
                    else cylinder.rejection_elastic_expansion.tenths_cc,
                    cylinder.water_capacity_tenths_l,
                    cylinder.tare_hundredths_lb,
                    cylinder.nominal_wall_thousandths_in,
                    cylinder.wall_source,
                    owner_id,
                    cylinder.status.value,
                    day_text(recorded_on),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"cylinder {cylinder.key} is already on the books") from exc
        return int(cursor.lastrowid or 0)

    def by_key(self, key: CylinderKey) -> Cylinder:
        row = self._one(
            f"{self._SELECT} WHERE c.manufacturer_symbol = ? AND c.serial = ?",
            (key.manufacturer_symbol, key.serial),
            f"no cylinder {key}",
        )
        return row_to_cylinder(row, as_text(row["owner_code"]))

    def id_of(self, key: CylinderKey) -> int:
        row = self._one(
            "SELECT id FROM cylinder WHERE manufacturer_symbol = ? AND serial = ?",
            (key.manufacturer_symbol, key.serial),
            f"no cylinder {key}",
        )
        return as_int(row["id"])

    def key_of(self, cylinder_id: int) -> CylinderKey:
        row = self._one(
            "SELECT manufacturer_symbol, serial FROM cylinder WHERE id = ?",
            (cylinder_id,),
            f"no cylinder with id {cylinder_id}",
        )
        return CylinderKey(as_text(row["manufacturer_symbol"]), as_text(row["serial"]))

    def exists(self, key: CylinderKey) -> bool:
        return (
            self._count(
                "SELECT count(*) FROM cylinder WHERE manufacturer_symbol = ? AND serial = ?",
                (key.manufacturer_symbol, key.serial),
            )
            > 0
        )

    def for_owner(self, owner_code: str) -> list[Cylinder]:
        rows = self._all(
            f"{self._SELECT} WHERE o.code = ? ORDER BY c.manufacturer_symbol, c.serial",
            (owner_code,),
        )
        return [row_to_cylinder(row, owner_code) for row in rows]

    def with_status(self, status: CylinderStatus) -> list[Cylinder]:
        rows = self._all(
            f"{self._SELECT} WHERE c.status = ? ORDER BY c.manufacturer_symbol, c.serial",
            (status.value,),
        )
        return [row_to_cylinder(row, as_text(row["owner_code"])) for row in rows]

    def in_service_of(self, service: GasService) -> list[Cylinder]:
        rows = self._all(
            f"{self._SELECT} WHERE c.service_code = ? ORDER BY c.serial",
            (service.code,),
        )
        return [row_to_cylinder(row, as_text(row["owner_code"])) for row in rows]

    def set_status(self, key: CylinderKey, status: CylinderStatus) -> Cylinder:
        current = self.by_key(key)
        moved = current.with_status(status)
        self.connection.execute(
            "UPDATE cylinder SET status = ? WHERE manufacturer_symbol = ? AND serial = ?",
            (moved.status.value, key.manufacturer_symbol, key.serial),
        )
        return moved

    def transfer(self, key: CylinderKey, owner_id: int) -> Cylinder:
        cylinder = self.by_key(key)
        if cylinder.status.is_terminal:
            raise ConflictError(f"{key} is {cylinder.status.value} and cannot change hands")
        self.connection.execute(
            "UPDATE cylinder SET owner_id = ? WHERE manufacturer_symbol = ? AND serial = ?",
            (owner_id, key.manufacturer_symbol, key.serial),
        )
        return self.by_key(key)

    def require(self, key: CylinderKey) -> Cylinder:
        cylinder = self.by_key(key)
        if not cylinder.status.accepts_work:
            raise NotFoundError(f"{key} is {cylinder.status.value} and takes no more work")
        return cylinder

    def record_wall(
        self, key: CylinderKey, taken_on: date, thousandths_in: int, source: str, note: str | None
    ) -> Cylinder:
        """File a wall reading and carry the latest one onto the cylinder.

        Readings accumulate because an ultrasonic sweep taken this year is
        worth keeping beside the data sheet figure it disagrees with, and the
        auditor asks which one was in force at the time of a test.
        """
        if thousandths_in <= 0:
            raise ConflictError("a wall reading has to be a positive measurement")
        cylinder_id = self.id_of(key)
        self.connection.execute(
            "INSERT INTO wall_reading (cylinder_id, taken_on, thousandths_in, source, note)"
            " VALUES (?, ?, ?, ?, ?)",
            (cylinder_id, day_text(taken_on), thousandths_in, source, note),
        )
        self.connection.execute(
            "UPDATE cylinder SET nominal_wall_thousandths_in = ?, wall_source = ? WHERE id = ?",
            (thousandths_in, source, cylinder_id),
        )
        return self.by_key(key)

    def wall_readings(self, key: CylinderKey) -> list[tuple[date, int, str]]:
        rows = self._all(
            "SELECT taken_on, thousandths_in, source FROM wall_reading"
            " WHERE cylinder_id = ? ORDER BY taken_on, id",
            (self.id_of(key),),
        )
        return [
            (as_day(row["taken_on"]), as_int(row["thousandths_in"]), as_text(row["source"]))
            for row in rows
        ]

    def count(self) -> int:
        return self._count("SELECT count(*) FROM cylinder")
