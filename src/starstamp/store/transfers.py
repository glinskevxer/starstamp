"""Who owned a cylinder, and when they stopped."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.store.repository import (
    Repository,
    as_day,
    as_optional_text,
    as_text,
    day_text,
)


@dataclass(frozen=True)
class Transfer:
    """One cylinder changing hands."""

    cylinder_key: str
    from_owner: str | None
    to_owner: str
    moved_on: date
    note: str | None = None

    def summary(self) -> str:
        head = f"{self.moved_on.isoformat()} {self.cylinder_key}"
        if self.from_owner is None:
            line = f"{head} taken on for {self.to_owner}"
        else:
            line = f"{head} {self.from_owner} to {self.to_owner}"
        return f"{line} ({self.note})" if self.note else line


def row_to_transfer(row: sqlite3.Row) -> Transfer:
    return Transfer(
        cylinder_key=as_text(row["cylinder_key"]),
        from_owner=as_optional_text(row["from_owner"]),
        to_owner=as_text(row["to_owner"]),
        moved_on=as_day(row["moved_on"]),
        note=as_optional_text(row["note"]),
    )


class TransferRepository(Repository):
    _SELECT = (
        "SELECT t.*, c.manufacturer_symbol || '/' || c.serial AS cylinder_key,"
        " f.code AS from_owner, o.code AS to_owner FROM ownership_transfer t"
        " JOIN cylinder c ON c.id = t.cylinder_id"
        " LEFT JOIN owner_account f ON f.id = t.from_owner_id"
        " JOIN owner_account o ON o.id = t.to_owner_id"
    )

    def add(
        self,
        cylinder_id: int,
        from_owner_id: int | None,
        to_owner_id: int,
        moved_on: date,
        note: str | None = None,
    ) -> None:
        self.connection.execute(
            "INSERT INTO ownership_transfer (cylinder_id, from_owner_id, to_owner_id,"
            " moved_on, note) VALUES (?, ?, ?, ?, ?)",
            (cylinder_id, from_owner_id, to_owner_id, day_text(moved_on), note),
        )

    def for_cylinder(self, key: CylinderKey) -> list[Transfer]:
        rows = self._all(
            f"{self._SELECT} WHERE c.manufacturer_symbol = ? AND c.serial = ?"
            " ORDER BY t.moved_on, t.id",
            (key.manufacturer_symbol, key.serial),
        )
        return [row_to_transfer(row) for row in rows]

    def owner_on(self, key: CylinderKey, day: date, current_owner: str) -> str:
        """Who owned it on a day, reading backwards from who owns it now."""
        for transfer in reversed(self.for_cylinder(key)):
            if transfer.moved_on <= day:
                return transfer.to_owner
            current_owner = transfer.from_owner or current_owner
        return current_owner

    def between(self, first: date, last: date) -> list[Transfer]:
        rows = self._all(
            f"{self._SELECT} WHERE t.moved_on BETWEEN ? AND ? ORDER BY t.moved_on, t.id",
            (day_text(first), day_text(last)),
        )
        return [row_to_transfer(row) for row in rows]

    def count(self) -> int:
        return self._count("SELECT count(*) FROM ownership_transfer")
