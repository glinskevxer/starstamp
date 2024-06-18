"""Reading and writing the test system's paperwork.

A certificate is never edited. When a calibration house restates one, the old
row is marked superseded and a new row goes in beside it, so an event from
before the restatement can still be shown resting on what was on the wall at
the time.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from fractions import Fraction

from starstamp.errors import ConflictError
from starstamp.model.calibration import (
    Certificate,
    SystemCheck,
    normalise_system_code,
)
from starstamp.model.units import Expansion
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_text,
    as_text,
    day_text,
)


def row_to_certificate(row: sqlite3.Row) -> Certificate:
    return Certificate(
        system_code=as_text(row["system_code"]),
        instrument=as_text(row["instrument"]),
        serial=as_text(row["serial"]),
        issued_on=as_day(row["issued_on"]),
        valid_until=as_day(row["valid_until"]),
        issued_by=as_text(row["issued_by"]),
        standard=as_text(row["standard"]),
    )


def row_to_check(row: sqlite3.Row) -> SystemCheck:
    return SystemCheck(
        system_code=as_text(row["system_code"]),
        day=as_day(row["checked_on"]),
        expected=Expansion(as_int(row["expected_tenths_cc"])),
        observed=Expansion(as_int(row["observed_tenths_cc"])),
        tolerance_percent=Fraction(
            as_int(row["tolerance_numerator"]), as_int(row["tolerance_denominator"])
        ),
        technician_badge=as_optional_text(row["technician_badge"]),
    )


class CalibrationRepository(Repository):
    def add_certificate(self, certificate: Certificate, note: str | None = None) -> int:
        cursor = self.connection.execute(
            "INSERT INTO calibration_certificate (system_code, instrument, serial, issued_on,"
            " valid_until, issued_by, standard, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                certificate.system_code,
                certificate.instrument,
                certificate.serial,
                day_text(certificate.issued_on),
                day_text(certificate.valid_until),
                certificate.issued_by,
                certificate.standard,
                note,
            ),
        )
        return int(cursor.lastrowid or 0)

    def certificates(self, system_code: str, *, standing_only: bool = True) -> list[Certificate]:
        wanted = normalise_system_code(system_code)
        clause = " AND superseded = 0" if standing_only else ""
        rows = self._all(
            "SELECT * FROM calibration_certificate WHERE system_code = ?"
            f"{clause} ORDER BY instrument, issued_on",
            (wanted,),
        )
        return [row_to_certificate(row) for row in rows]

    def in_force(self, system_code: str, day: date) -> list[Certificate]:
        """The certificates that covered a system on a given day."""
        return [
            certificate
            for certificate in self.certificates(system_code)
            if certificate.valid_on(day)
        ]

    def by_id(self, certificate_id: int) -> Certificate:
        return row_to_certificate(
            self._one(
                "SELECT * FROM calibration_certificate WHERE id = ?",
                (certificate_id,),
                f"no certificate {certificate_id}",
            )
        )

    def id_of(self, system_code: str, instrument: str, serial: str) -> int:
        row = self._one(
            "SELECT id FROM calibration_certificate WHERE system_code = ? AND instrument = ?"
            " AND serial = ? AND superseded = 0",
            (normalise_system_code(system_code), instrument, serial),
            f"no standing {instrument} certificate for {serial}",
        )
        return as_int(row["id"])

    def supersede(self, certificate_id: int, note: str) -> None:
        row = self._one(
            "SELECT superseded FROM calibration_certificate WHERE id = ?",
            (certificate_id,),
            f"no certificate {certificate_id}",
        )
        if as_int(row["superseded"]):
            raise ConflictError(f"certificate {certificate_id} was already superseded")
        self.connection.execute(
            "UPDATE calibration_certificate SET superseded = 1, note = ? WHERE id = ?",
            (note, certificate_id),
        )

    def record_check(self, check: SystemCheck) -> int:
        try:
            cursor = self.connection.execute(
                "INSERT INTO system_check (system_code, checked_on, expected_tenths_cc,"
                " observed_tenths_cc, tolerance_numerator, tolerance_denominator,"
                " technician_badge) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    check.system_code,
                    day_text(check.day),
                    check.expected.tenths_cc,
                    check.observed.tenths_cc,
                    check.tolerance_percent.numerator,
                    check.tolerance_percent.denominator,
                    check.technician_badge,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(
                f"{check.system_code} already has a check for {check.day.isoformat()}"
            ) from exc
        return int(cursor.lastrowid or 0)

    def check_on(self, system_code: str, day: date) -> SystemCheck | None:
        row = self.connection.execute(
            "SELECT * FROM system_check WHERE system_code = ? AND checked_on = ?",
            (normalise_system_code(system_code), day_text(day)),
        ).fetchone()
        return None if row is None else row_to_check(row)

    def checks_between(self, system_code: str, first: date, last: date) -> list[SystemCheck]:
        rows = self._all(
            "SELECT * FROM system_check WHERE system_code = ? AND checked_on BETWEEN ? AND ?"
            " ORDER BY checked_on",
            (normalise_system_code(system_code), day_text(first), day_text(last)),
        )
        return [row_to_check(row) for row in rows]

    def systems(self) -> list[str]:
        rows = self._all(
            "SELECT DISTINCT system_code FROM calibration_certificate ORDER BY system_code"
        )
        return [as_text(row["system_code"]) for row in rows]
