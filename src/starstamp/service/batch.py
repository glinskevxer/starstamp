"""A day's bench work, entered from the sheet it was written on.

The rig prints a strip and the operator writes the cylinder against it. Typing
that in one command at a time is where the shop's data entry errors come from,
so this takes the sheet as it stands: one row per cylinder, and it stops on
nothing. Every row that will not go through is reported with its line number,
and the rest are recorded.

Nothing here is a shortcut around the rules. Each row goes through the same
service the single cylinder command does, so a row that would be refused at
the bench is refused here.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

from starstamp.errors import StarstampError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind, Observation, parse_thousandths
from starstamp.model.method import Method
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion, Pressure
from starstamp.service.requalify import (
    RequalificationRequest,
    RequalificationResult,
    RequalificationService,
)
from starstamp.store.db import Book

COLUMNS = ("cylinder", "applied", "total", "permanent")


@dataclass(frozen=True)
class RowFault:
    """One line of the sheet that will not go through."""

    line: int
    cylinder: str
    detail: str

    def __str__(self) -> str:
        return f"line {self.line} ({self.cylinder}): {self.detail}"


@dataclass(frozen=True)
class BatchResult:
    """What a sheet did."""

    day: date
    results: tuple[RequalificationResult, ...]
    faults: tuple[RowFault, ...]

    @property
    def recorded(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for item in self.results if item.event.outcome.may_be_marked)

    @property
    def is_clean(self) -> bool:
        return not self.faults

    def describe(self) -> str:
        head = (
            f"{self.day.isoformat()}: {self.recorded} recorded, {self.passed} passed, "
            f"{len(self.faults)} rows left out"
        )
        if not self.faults:
            return head
        return "\n".join([head, *[f"  {fault}" for fault in self.faults]])


def _observations(text: str) -> tuple[Observation, ...]:
    found: list[Observation] = []
    for item in text.split(";"):
        cleaned = item.strip()
        if not cleaned:
            continue
        kind, _, depth = cleaned.partition(":")
        found.append(
            Observation(
                kind=DefectKind.parse(kind),
                depth_thousandths_in=parse_thousandths(depth) if depth else None,
            )
        )
    return tuple(found)


class BatchService:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.requalify = RequalificationService(book)

    def run(
        self,
        text: str,
        day: date,
        technician_badge: str,
        system_code: str,
        *,
        method: Method = Method.VOLUMETRIC,
        hold_seconds: int = 30,
    ) -> BatchResult:
        """Work through a sheet, recording what will go and reporting what will not."""
        reader = csv.DictReader(io.StringIO(text))
        missing = [name for name in COLUMNS if name not in (reader.fieldnames or [])]
        if missing:
            raise StarstampError(f"the sheet is missing columns: {', '.join(missing)}")

        results: list[RequalificationResult] = []
        faults: list[RowFault] = []
        for line, row in enumerate(reader, start=2):
            raw = (row.get("cylinder") or "").strip()
            try:
                request = RequalificationRequest(
                    key=CylinderKey.parse(raw),
                    day=day,
                    technician_badge=technician_badge,
                    method=method,
                    system_code=system_code,
                    observations=_observations(row.get("defects") or ""),
                    readings=PressureReadings(
                        applied=Pressure.parse(row["applied"]),
                        hold_seconds=int(row.get("hold") or hold_seconds),
                        total_expansion=Expansion.parse(row["total"]),
                        permanent_expansion=Expansion.parse(row["permanent"]),
                    ),
                )
                results.append(self.requalify.perform(request))
            except StarstampError as exc:
                faults.append(RowFault(line, raw or "?", str(exc)))
            except (KeyError, ValueError) as exc:
                faults.append(RowFault(line, raw or "?", f"unreadable row: {exc}"))
        return BatchResult(day, tuple(results), tuple(faults))
