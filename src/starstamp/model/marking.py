"""Restoring marks a cylinder has worn off.

Twenty years of being dragged across a truck bed takes the stamping off a
cylinder's shoulder, and a cylinder whose marks cannot be read cannot be
filled. It can be re-marked, but only with what was there before: the
requalifier is restoring a record, not making one, and the difference is the
whole of the regulation.

So a re-marking names what it restored and what it restored it from. Nothing
here invents a specification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

from starstamp.errors import ValidationError

_MARK = re.compile(r"^[A-Z0-9][A-Z0-9 \-./+*]{0,31}$")


class MarkKind(Enum):
    """Which of a cylinder's marks was restored."""

    SPECIFICATION = "specification"
    SERIAL = "serial"
    MANUFACTURER = "manufacturer"
    MANUFACTURE_DATE = "manufacture_date"
    SERVICE_PRESSURE = "service_pressure"
    REJECTION_LIMIT = "rejection_limit"
    TARE_WEIGHT = "tare_weight"

    @property
    def is_identity(self) -> bool:
        """Marks that say which cylinder this is rather than what it is."""
        return self in {MarkKind.SERIAL, MarkKind.MANUFACTURER}

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")


class Evidence(Enum):
    """What the shop restored the mark from."""

    OUR_RECORDS = "our_records"
    OWNER_DECLARATION = "owner_declaration"
    MANUFACTURER_LETTER = "manufacturer_letter"

    @property
    def is_ours(self) -> bool:
        return self is Evidence.OUR_RECORDS

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")


def normalise_mark(text: str) -> str:
    cleaned = " ".join(text.strip().upper().split())
    if not _MARK.match(cleaned):
        raise ValidationError(f"that is not something stamped on a cylinder: {text!r}")
    return cleaned


@dataclass(frozen=True)
class RestoredMark:
    """One mark, and what it now reads."""

    kind: MarkKind
    reads: str

    def __post_init__(self) -> None:
        normalise_mark(self.reads)

    def __str__(self) -> str:
        return f"{self.kind.label} {self.reads}"


@dataclass(frozen=True)
class Remarking:
    """One cylinder re-marked, on one day, by one shop."""

    cylinder_key: str
    marked_on: date
    facility_rin: str
    technician_badge: str
    evidence: Evidence
    marks: tuple[RestoredMark, ...]
    note: str | None = None
    remarking_id: int | None = None

    def __post_init__(self) -> None:
        if not self.marks:
            raise ValidationError("a re-marking that restored nothing is not a re-marking")
        kinds = [mark.kind for mark in self.marks]
        if len(set(kinds)) != len(kinds):
            raise ValidationError("the same mark was restored twice in one go")

    @property
    def restored_identity(self) -> bool:
        return any(mark.kind.is_identity for mark in self.marks)

    def of_kind(self, kind: MarkKind) -> RestoredMark | None:
        for mark in self.marks:
            if mark.kind is kind:
                return mark
        return None

    def summary(self) -> str:
        marks = ", ".join(str(mark) for mark in self.marks)
        line = (
            f"{self.marked_on.isoformat()} {self.cylinder_key} re-marked under "
            f"{self.facility_rin} from {self.evidence.label}: {marks}"
        )
        return f"{line} ({self.note})" if self.note else line
