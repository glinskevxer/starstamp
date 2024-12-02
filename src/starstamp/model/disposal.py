"""What becomes of a cylinder after it is condemned.

A condemned cylinder is worth money as scrap and is lethal if it goes back
into service, which is why the regulation is not about paperwork: the shop has
to render it incapable of holding pressure. Drilling it, cutting the neck off
or crushing it all count. Putting a sticker on it does not.

The owner can ask for it back, and they are entitled to it, rendered.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from starstamp.errors import ValidationError

RENDER_WITHIN_DAYS = 30


class DisposalMethod(Enum):
    """How the cylinder was rendered, or why it has not been."""

    DRILLED = "drilled"
    NECK_CUT = "neck_cut"
    CRUSHED = "crushed"
    SAWN = "sawn"
    HELD_FOR_OWNER = "held_for_owner"

    @property
    def renders_it_useless(self) -> bool:
        return self is not DisposalMethod.HELD_FOR_OWNER

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")

    @classmethod
    def parse(cls, text: str) -> DisposalMethod:
        cleaned = text.strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "drill": cls.DRILLED,
            "hole": cls.DRILLED,
            "cut": cls.NECK_CUT,
            "neck": cls.NECK_CUT,
            "crush": cls.CRUSHED,
            "saw": cls.SAWN,
            "hold": cls.HELD_FOR_OWNER,
        }
        if cleaned in aliases:
            return aliases[cleaned]
        try:
            return cls(cleaned)
        except ValueError as exc:
            known = ", ".join(item.value for item in cls)
            raise ValidationError(f"unknown disposal {text!r}; the shop does {known}") from exc


@dataclass(frozen=True)
class Disposal:
    """One cylinder, dealt with."""

    cylinder_key: str
    method: DisposalMethod
    performed_on: date
    technician_badge: str
    condemned_on: date
    witness_badge: str | None = None
    scrap_ticket: str | None = None
    returned_to_owner: bool = False
    note: str | None = None
    disposal_id: int | None = None

    def __post_init__(self) -> None:
        if self.performed_on < self.condemned_on:
            raise ValidationError("a cylinder cannot be dealt with before it was condemned")
        if self.returned_to_owner and not self.method.renders_it_useless:
            raise ValidationError("a cylinder going back to its owner has to be rendered first")
        if self.witness_badge is not None and self.witness_badge == self.technician_badge:
            raise ValidationError("a witness has to be somebody else")

    @property
    def due_by(self) -> date:
        return self.condemned_on + timedelta(days=RENDER_WITHIN_DAYS)

    @property
    def is_late(self) -> bool:
        if not self.method.renders_it_useless:
            return False
        return self.performed_on > self.due_by

    @property
    def days_taken(self) -> int:
        return (self.performed_on - self.condemned_on).days

    def summary(self) -> str:
        line = (
            f"{self.performed_on.isoformat()} {self.cylinder_key} {self.method.label}"
            f" by {self.technician_badge}"
        )
        if self.witness_badge:
            line = f"{line}, witnessed by {self.witness_badge}"
        if self.scrap_ticket:
            line = f"{line}, ticket {self.scrap_ticket}"
        if self.returned_to_owner:
            line = f"{line}, returned to the owner"
        if self.is_late:
            line = f"{line}, {self.days_taken} days after condemnation"
        return line
