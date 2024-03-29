"""Reading and writing the shop's own approvals."""

from __future__ import annotations

import sqlite3

from starstamp.errors import ConflictError
from starstamp.model.facility import Facility, Technician, normalise_badge, normalise_rin
from starstamp.model.method import Method
from starstamp.store.repository import (
    Repository,
    as_day,
    as_optional_day,
    as_optional_text,
    as_text,
    day_text,
    optional_day_text,
)


def pack_methods(methods: frozenset[Method]) -> str:
    return ",".join(sorted(method.value for method in methods))


def unpack_methods(text: str) -> frozenset[Method]:
    return frozenset(Method(item) for item in text.split(",") if item)


def row_to_facility(row: sqlite3.Row) -> Facility:
    return Facility(
        rin=as_text(row["rin"]),
        name=as_text(row["name"]),
        approved_from=as_day(row["approved_from"]),
        approved_until=as_day(row["approved_until"]),
        methods=unpack_methods(as_text(row["methods"])),
        address=as_optional_text(row["address"]),
    )


def row_to_technician(row: sqlite3.Row) -> Technician:
    return Technician(
        badge=as_text(row["badge"]),
        name=as_text(row["name"]),
        methods=unpack_methods(as_text(row["methods"])),
        qualified_from=as_day(row["qualified_from"]),
        qualified_until=as_optional_day(row["qualified_until"]),
    )


class FacilityRepository(Repository):
    def add(self, facility: Facility) -> int:
        try:
            cursor = self.connection.execute(
                "INSERT INTO facility (rin, name, address, approved_from, approved_until, methods)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    facility.rin,
                    facility.name,
                    facility.address,
                    day_text(facility.approved_from),
                    day_text(facility.approved_until),
                    pack_methods(facility.methods),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"RIN {facility.rin} is already recorded") from exc
        return int(cursor.lastrowid or 0)

    def by_rin(self, rin: str) -> Facility:
        wanted = normalise_rin(rin)
        return row_to_facility(
            self._one("SELECT * FROM facility WHERE rin = ?", (wanted,), f"no facility {wanted}")
        )

    def all(self) -> list[Facility]:
        return [row_to_facility(row) for row in self._all("SELECT * FROM facility ORDER BY rin")]

    def only(self) -> Facility:
        """The shop's own RIN, when the book holds exactly one."""
        found = self.all()
        if not found:
            raise ConflictError("this book has no facility recorded; add the shop's RIN first")
        if len(found) > 1:
            raise ConflictError("this book holds more than one RIN; name the one you mean")
        return found[0]

    def renew(self, rin: str, approved_until: str) -> Facility:
        facility = self.by_rin(rin)
        self.connection.execute(
            "UPDATE facility SET approved_until = ? WHERE rin = ?",
            (approved_until, facility.rin),
        )
        return self.by_rin(rin)


class TechnicianRepository(Repository):
    def add(self, technician: Technician) -> int:
        try:
            cursor = self.connection.execute(
                "INSERT INTO technician (badge, name, methods, qualified_from, qualified_until)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    technician.badge,
                    technician.name,
                    pack_methods(technician.methods),
                    day_text(technician.qualified_from),
                    optional_day_text(technician.qualified_until),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"badge {technician.badge} is already on the bench") from exc
        return int(cursor.lastrowid or 0)

    def by_badge(self, badge: str) -> Technician:
        wanted = normalise_badge(badge)
        return row_to_technician(
            self._one(
                "SELECT * FROM technician WHERE badge = ?", (wanted,), f"no technician {wanted}"
            )
        )

    def all(self) -> list[Technician]:
        return [
            row_to_technician(row) for row in self._all("SELECT * FROM technician ORDER BY badge")
        ]

    def qualified_for(self, method: Method) -> list[Technician]:
        return [item for item in self.all() if method in item.methods]
