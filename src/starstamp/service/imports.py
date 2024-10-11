"""Taking a customer's cylinder list into the book.

A new account turns up with a spreadsheet of four hundred cylinders, half of
which have a serial nobody can read and a specification somebody typed from
memory. The import therefore reports every bad row rather than stopping at the
first, and it will not write anything at all unless asked: a dry run against
the real book is the only way to find out what a list is going to do.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

from starstamp.errors import ConflictError, StarstampError
from starstamp.model.cylinder import Cylinder, CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import parse_thousandths
from starstamp.model.service import lookup_service
from starstamp.model.specification import parse_specification
from starstamp.model.units import Expansion
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.owners import OwnerRepository

REQUIRED_COLUMNS = ("cylinder", "specification", "manufactured", "service")


@dataclass(frozen=True)
class RowProblem:
    """One row that will not go in, and why."""

    line: int
    detail: str
    raw: str

    def __str__(self) -> str:
        return f"line {self.line}: {self.detail} [{self.raw}]"


@dataclass(frozen=True)
class ImportResult:
    """What an import did, or would have done."""

    owner_code: str
    accepted: tuple[Cylinder, ...]
    problems: tuple[RowProblem, ...]
    written: bool

    @property
    def is_clean(self) -> bool:
        return not self.problems

    def describe(self) -> str:
        verb = "took in" if self.written else "would take in"
        head = f"{verb} {len(self.accepted)} cylinders for {self.owner_code}"
        if not self.problems:
            return head
        lines = [f"{head}, {len(self.problems)} rows left out"]
        lines.extend(f"  {problem}" for problem in self.problems)
        return "\n".join(lines)


def _row_to_cylinder(row: dict[str, str], owner_code: str) -> Cylinder:
    key = CylinderKey.parse(row["cylinder"])
    ree = (row.get("ree") or "").strip()
    wall = (row.get("wall") or "").strip()
    return Cylinder(
        key=key,
        specification=parse_specification(row["specification"]),
        manufactured=StampedMonth.parse(row["manufactured"]),
        service=lookup_service(row["service"]),
        owner_code=owner_code,
        rejection_elastic_expansion=Expansion.parse(ree) if ree else None,
        nominal_wall_thousandths_in=parse_thousandths(wall) if wall else None,
        wall_source="customer list" if wall else None,
    )


class ImportService:
    def __init__(self, book: Book) -> None:
        self.book = book
        self.cylinders = CylinderRepository(book.connection)
        self.owners = OwnerRepository(book.connection)

    def read(self, text: str, owner_code: str, day: date, *, write: bool) -> ImportResult:
        """Read a customer list, reporting every row that will not go in."""
        owner = self.owners.require_open(owner_code, day)
        reader = csv.DictReader(io.StringIO(text))
        missing = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or [])]
        if missing:
            raise ConflictError(f"the list is missing columns: {', '.join(missing)}")

        accepted: list[Cylinder] = []
        problems: list[RowProblem] = []
        seen: set[CylinderKey] = set()
        for line, row in enumerate(reader, start=2):
            raw = ",".join((row.get(name) or "").strip() for name in REQUIRED_COLUMNS)
            try:
                cylinder = _row_to_cylinder(row, owner.code)
            except StarstampError as exc:
                problems.append(RowProblem(line, str(exc), raw))
                continue
            if cylinder.key in seen:
                problems.append(RowProblem(line, f"{cylinder.key} is twice in this list", raw))
                continue
            if self.cylinders.exists(cylinder.key):
                problems.append(RowProblem(line, f"{cylinder.key} is already on the books", raw))
                continue
            seen.add(cylinder.key)
            accepted.append(cylinder)

        if write:
            owner_id = self.owners.id_of(owner.code)
            for cylinder in accepted:
                self.cylinders.add(cylinder, owner_id, day)
        return ImportResult(owner.code, tuple(accepted), tuple(problems), write)
