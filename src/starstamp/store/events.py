"""Reading and writing records of test.

Nothing in here updates a row's readings. The only column that ever changes
after a row is written is the state, and it changes in one direction, from
recorded to reversed. Everything else is a new row.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.acetylene import AcetyleneExam
from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind, Observation
from starstamp.model.event import EventState, Outcome, RequalificationEvent
from starstamp.model.method import Method
from starstamp.model.testrecord import PressureReadings
from starstamp.model.ultrasonic import Band, Position, Reading, Scan
from starstamp.model.units import Expansion, Pressure
from starstamp.rules.visual import Finding, VisualResult
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_int,
    as_optional_text,
    as_text,
    day_text,
)

SEPARATOR = "\n"


def pack_lines(lines: tuple[str, ...]) -> str:
    return SEPARATOR.join(lines)


def unpack_lines(text: str) -> tuple[str, ...]:
    return tuple(line for line in text.split(SEPARATOR) if line)


def row_to_event(row: sqlite3.Row, key: CylinderKey) -> RequalificationEvent:
    applied = as_optional_int(row["applied_psig"])
    total = as_optional_int(row["total_tenths_cc"])
    permanent = as_optional_int(row["permanent_tenths_cc"])
    readings = None
    if applied is not None:
        readings = PressureReadings(
            applied=Pressure(applied),
            hold_seconds=as_int(row["hold_seconds"]),
            total_expansion=None if total is None else Expansion(total),
            permanent_expansion=None if permanent is None else Expansion(permanent),
            leaked=bool(as_int(row["leaked"])),
            distorted=bool(as_int(row["distorted"])),
        )
    return RequalificationEvent(
        cylinder=key,
        performed_on=as_day(row["performed_on"]),
        method=Method(as_text(row["method"])),
        facility_rin=as_text(row["facility_rin"]),
        technician_badge=as_text(row["technician_badge"]),
        outcome=Outcome(as_text(row["outcome"])),
        reasons=unpack_lines(as_text(row["reasons"])),
        system_code=as_optional_text(row["system_code"]),
        readings=readings,
        wall_thousandths_in=as_optional_int(row["wall_thousandths_in"]),
        state=EventState(as_text(row["state"])),
        starred=bool(as_int(row["starred"])),
        plus_rated=bool(as_int(row["plus_rated"])),
        star_refused=unpack_lines(as_text(row["star_refused"])),
        plus_refused=unpack_lines(as_text(row["plus_refused"])),
        reverses=as_optional_int(row["reverses_id"]),
        event_id=as_int(row["id"]),
        notes=unpack_lines(as_text(row["notes"])),
    )


class EventRepository(Repository):
    """Records of test, joined back to the cylinder they belong to."""

    _SELECT = (
        "SELECT r.*, c.manufacturer_symbol AS symbol, c.serial AS serial"
        " FROM requalification r JOIN cylinder c ON c.id = r.cylinder_id"
    )

    def add(
        self,
        event: RequalificationEvent,
        cylinder_id: int,
        findings: list[Finding] | None = None,
    ) -> RequalificationEvent:
        readings = event.readings
        cursor = self.connection.execute(
            "INSERT INTO requalification (cylinder_id, performed_on, method, facility_rin,"
            " technician_badge, system_code, outcome, reasons, notes, applied_psig, hold_seconds,"
            " total_tenths_cc, permanent_tenths_cc, leaked, distorted, wall_thousandths_in,"
            " state, reverses_id, starred, plus_rated, star_refused, plus_refused, recorded_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cylinder_id,
                day_text(event.performed_on),
                event.method.value,
                event.facility_rin,
                event.technician_badge,
                event.system_code,
                event.outcome.value,
                pack_lines(event.reasons),
                pack_lines(event.notes),
                None if readings is None else readings.applied.psig,
                None if readings is None else readings.hold_seconds,
                None
                if readings is None or readings.total_expansion is None
                else readings.total_expansion.tenths_cc,
                None
                if readings is None or readings.permanent_expansion is None
                else readings.permanent_expansion.tenths_cc,
                0 if readings is None else int(readings.leaked),
                0 if readings is None else int(readings.distorted),
                event.wall_thousandths_in,
                event.state.value,
                event.reverses,
                int(event.starred),
                int(event.plus_rated),
                pack_lines(event.star_refused),
                pack_lines(event.plus_refused),
                datetime.now(tz=UTC).isoformat(timespec="seconds"),
            ),
        )
        event_id = int(cursor.lastrowid or 0)
        for finding in findings or []:
            self.connection.execute(
                "INSERT INTO requalification_finding (requalification_id, kind,"
                " depth_thousandths_in, length_thousandths_in, result, reason, note)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    finding.observation.kind.value,
                    finding.observation.depth_thousandths_in,
                    finding.observation.length_thousandths_in,
                    finding.result.value,
                    finding.reason,
                    finding.observation.note,
                ),
            )
        return event.with_id(event_id)

    def add_scan(self, event_id: int, scan: Scan) -> None:
        """File the ultrasonic readings that go with a record of test."""
        for reading in scan.readings:
            self.connection.execute(
                "INSERT INTO ultrasonic_reading (requalification_id, band, position_index,"
                " thousandths_in) VALUES (?, ?, ?, ?)",
                (
                    event_id,
                    reading.position.band.value,
                    reading.position.index,
                    reading.thousandths_in,
                ),
            )

    def scan_for(self, event_id: int) -> Scan:
        rows = self._all(
            "SELECT * FROM ultrasonic_reading WHERE requalification_id = ?"
            " ORDER BY band, position_index",
            (event_id,),
        )
        return Scan(
            tuple(
                Reading(
                    Position(Band(as_text(row["band"])), as_int(row["position_index"])),
                    as_int(row["thousandths_in"]),
                )
                for row in rows
            )
        )

    def add_acetylene_exam(self, event_id: int, exam: AcetyleneExam, marked: int) -> None:
        """File the weighing that goes with an acetylene record of test."""
        self.connection.execute(
            "INSERT INTO acetylene_exam (requalification_id, tare_now_hundredths_lb,"
            " marked_hundredths_lb, fuse_plugs_sound, mass_settled, shell_sound, cap_sound,"
            " note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                exam.tare_now_hundredths_lb,
                marked,
                int(exam.fuse_plugs_sound),
                int(exam.mass_settled),
                int(exam.shell_sound),
                int(exam.cap_sound),
                exam.note,
            ),
        )

    def acetylene_exam(self, event_id: int) -> AcetyleneExam | None:
        row = self.connection.execute(
            "SELECT * FROM acetylene_exam WHERE requalification_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            return None
        return AcetyleneExam(
            tare_now_hundredths_lb=as_int(row["tare_now_hundredths_lb"]),
            fuse_plugs_sound=bool(as_int(row["fuse_plugs_sound"])),
            mass_settled=bool(as_int(row["mass_settled"])),
            shell_sound=bool(as_int(row["shell_sound"])),
            cap_sound=bool(as_int(row["cap_sound"])),
            note=as_optional_text(row["note"]),
        )

    def by_id(self, event_id: int) -> RequalificationEvent:
        row = self._one(
            f"{self._SELECT} WHERE r.id = ?", (event_id,), f"no record of test {event_id}"
        )
        return row_to_event(row, CylinderKey(as_text(row["symbol"]), as_text(row["serial"])))

    def for_cylinder(
        self, key: CylinderKey, *, standing_only: bool = False
    ) -> list[RequalificationEvent]:
        rows = self._all(
            f"{self._SELECT} WHERE c.manufacturer_symbol = ? AND c.serial = ?"
            " ORDER BY r.performed_on, r.id",
            (key.manufacturer_symbol, key.serial),
        )
        events = [row_to_event(row, key) for row in rows]
        if standing_only:
            return [event for event in events if event.state.stands]
        return events

    def latest_pass(self, key: CylinderKey) -> RequalificationEvent | None:
        for event in reversed(self.for_cylinder(key, standing_only=True)):
            if event.outcome is Outcome.PASS:
                return event
        return None

    def on_day(self, day: date) -> list[RequalificationEvent]:
        rows = self._all(f"{self._SELECT} WHERE r.performed_on = ? ORDER BY r.id", (day_text(day),))
        return [
            row_to_event(row, CylinderKey(as_text(row["symbol"]), as_text(row["serial"])))
            for row in rows
        ]

    def for_system_between(
        self, system_code: str, first: date, last: date
    ) -> list[RequalificationEvent]:
        rows = self._all(
            f"{self._SELECT} WHERE r.system_code = ? AND r.performed_on BETWEEN ? AND ?"
            " ORDER BY r.performed_on, r.id",
            (system_code, day_text(first), day_text(last)),
        )
        return [
            row_to_event(row, CylinderKey(as_text(row["symbol"]), as_text(row["serial"])))
            for row in rows
        ]

    def between(self, first: date, last: date) -> list[RequalificationEvent]:
        """Every record in a window, whichever rig produced it."""
        rows = self._all(
            f"{self._SELECT} WHERE r.performed_on BETWEEN ? AND ? ORDER BY r.performed_on, r.id",
            (day_text(first), day_text(last)),
        )
        return [
            row_to_event(row, CylinderKey(as_text(row["symbol"]), as_text(row["serial"])))
            for row in rows
        ]

    def for_owner_between(
        self, owner_code: str, first: date, last: date
    ) -> list[RequalificationEvent]:
        """Records in a window against the cylinders one account owns now."""
        rows = self._all(
            f"{self._SELECT} JOIN owner_account o ON o.id = c.owner_id"
            " WHERE o.code = ? AND r.performed_on BETWEEN ? AND ?"
            " ORDER BY r.performed_on, r.id",
            (owner_code.upper(), day_text(first), day_text(last)),
        )
        return [
            row_to_event(row, CylinderKey(as_text(row["symbol"]), as_text(row["serial"])))
            for row in rows
        ]

    def reverse(self, event_id: int, reason: str) -> RequalificationEvent:
        event = self.by_id(event_id)
        if event.state is EventState.REVERSED:
            raise ConflictError(f"record of test {event_id} was already reversed")
        reversed_event = event.reversed_by(reason)
        self.connection.execute(
            "UPDATE requalification SET state = ?, notes = ? WHERE id = ?",
            (EventState.REVERSED.value, pack_lines(reversed_event.notes), event_id),
        )
        return self.by_id(event_id)

    def observations(self, event_id: int) -> list[tuple[Observation, VisualResult, str]]:
        rows = self._all(
            "SELECT * FROM requalification_finding WHERE requalification_id = ? ORDER BY id",
            (event_id,),
        )
        out: list[tuple[Observation, VisualResult, str]] = []
        for row in rows:
            observation = Observation(
                kind=DefectKind(as_text(row["kind"])),
                depth_thousandths_in=as_optional_int(row["depth_thousandths_in"]),
                length_thousandths_in=as_optional_int(row["length_thousandths_in"]),
                note=as_optional_text(row["note"]),
            )
            out.append((observation, VisualResult(as_text(row["result"])), as_text(row["reason"])))
        return out

    def require_standing(self, event_id: int) -> RequalificationEvent:
        event = self.by_id(event_id)
        if not event.state.stands:
            raise NotFoundError(f"record of test {event_id} has been reversed")
        return event

    def count(self) -> int:
        return self._count("SELECT count(*) FROM requalification")
