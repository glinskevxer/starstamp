"""Work done to a cylinder that is not a requalification.

A repair is what happens between a suspended requalification and the one that
follows it. Some repairs are ordinary shop work and some of them are only
legal on certain cylinders at all, which is why the kind is an enum rather
than a note in a text field.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from starstamp.errors import ValidationError


class RepairKind(Enum):
    """What was done."""

    VALVE_REPLACEMENT = "valve_replacement"
    NECK_THREAD_REPAIR = "neck_thread_repair"
    REMARKING = "remarking"
    CLEANING = "cleaning"
    TUMBLING = "tumbling"
    PAINTING = "painting"
    FOOTRING_REPLACEMENT = "footring_replacement"
    WELD_REPAIR = "weld_repair"
    HEAT_TREATMENT = "heat_treatment"

    @property
    def touches_the_pressure_envelope(self) -> bool:
        """Whether the repair changes the metal that holds the gas in."""
        return self in {
            RepairKind.WELD_REPAIR,
            RepairKind.HEAT_TREATMENT,
            RepairKind.NECK_THREAD_REPAIR,
        }

    @property
    def needs_a_requalification_after(self) -> bool:
        """Whether the cylinder has to be tested again before it is filled."""
        return self.touches_the_pressure_envelope

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")

    @classmethod
    def parse(cls, text: str) -> RepairKind:
        cleaned = text.strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "valve": cls.VALVE_REPLACEMENT,
            "threads": cls.NECK_THREAD_REPAIR,
            "remark": cls.REMARKING,
            "clean": cls.CLEANING,
            "tumble": cls.TUMBLING,
            "paint": cls.PAINTING,
            "footring": cls.FOOTRING_REPLACEMENT,
            "weld": cls.WELD_REPAIR,
            "heat_treat": cls.HEAT_TREATMENT,
        }
        if cleaned in aliases:
            return aliases[cleaned]
        try:
            return cls(cleaned)
        except ValueError as exc:
            known = ", ".join(item.value for item in cls)
            raise ValidationError(f"unknown repair {text!r}; the shop does {known}") from exc


@dataclass(frozen=True)
class Repair:
    """One piece of work on one cylinder."""

    cylinder_key: str
    kind: RepairKind
    performed_on: date
    technician_badge: str
    facility_rin: str | None = None
    note: str | None = None
    parts: str | None = None
    repair_id: int | None = None

    def __post_init__(self) -> None:
        if self.kind.touches_the_pressure_envelope and self.facility_rin is None:
            raise ValidationError(f"{self.kind.label} has to be done under a requalifier's number")
        if self.kind is RepairKind.VALVE_REPLACEMENT and not self.parts:
            raise ValidationError("a valve change has to say what valve went in")

    def summary(self) -> str:
        line = f"{self.performed_on.isoformat()} {self.cylinder_key} {self.kind.label}"
        if self.parts:
            line = f"{line}, {self.parts}"
        if self.note:
            line = f"{line} ({self.note})"
        return line
