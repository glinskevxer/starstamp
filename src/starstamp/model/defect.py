"""What the inspector writes down when a cylinder comes across the bench.

An observation is a measurement, not a verdict. Whether a sixteen thousandth
deep pit condemns a cylinder depends on how thick its wall was to begin with
and what it is made of, and neither of those is known here. So this module
records what was seen and leaves the deciding to the rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from starstamp.errors import ValidationError

_LENGTH = re.compile(r"^(?P<whole>\d+)(?:\.(?P<frac>\d{1,3}))?$")


class DefectKind(Enum):
    """The conditions a visual inspection looks for."""

    GENERAL_CORROSION = "general_corrosion"
    ISOLATED_PITTING = "isolated_pitting"
    LINE_CORROSION = "line_corrosion"
    CREVICE_CORROSION = "crevice_corrosion"
    DENT = "dent"
    CUT_GOUGE_DIG = "cut_gouge_dig"
    BULGE = "bulge"
    CRACK = "crack"
    FIRE_DAMAGE = "fire_damage"
    ARC_BURN = "arc_burn"
    TORCH_BURN = "torch_burn"
    NECK_DAMAGE = "neck_damage"
    THREAD_DAMAGE = "thread_damage"
    LEAK = "leak"
    ILLEGIBLE_MARKING = "illegible_marking"
    FOOTRING_DAMAGE = "footring_damage"
    INTERIOR_CORROSION = "interior_corrosion"

    @property
    def is_measured_by_depth(self) -> bool:
        """Whether a depth reading is part of recording this at all."""
        return self in {
            DefectKind.GENERAL_CORROSION,
            DefectKind.ISOLATED_PITTING,
            DefectKind.LINE_CORROSION,
            DefectKind.CREVICE_CORROSION,
            DefectKind.CUT_GOUGE_DIG,
            DefectKind.DENT,
            DefectKind.INTERIOR_CORROSION,
        }

    @property
    def wants_a_length(self) -> bool:
        return self in {
            DefectKind.LINE_CORROSION,
            DefectKind.CREVICE_CORROSION,
            DefectKind.CUT_GOUGE_DIG,
            DefectKind.CRACK,
        }

    @property
    def is_structural(self) -> bool:
        """Damage to the pressure envelope rather than to a fitting."""
        return self not in {
            DefectKind.THREAD_DAMAGE,
            DefectKind.ILLEGIBLE_MARKING,
            DefectKind.FOOTRING_DAMAGE,
        }

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")

    @classmethod
    def parse(cls, text: str) -> DefectKind:
        cleaned = text.strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "pitting": cls.ISOLATED_PITTING,
            "pit": cls.ISOLATED_PITTING,
            "gouge": cls.CUT_GOUGE_DIG,
            "cut": cls.CUT_GOUGE_DIG,
            "dig": cls.CUT_GOUGE_DIG,
            "corrosion": cls.GENERAL_CORROSION,
            "burn": cls.ARC_BURN,
            "fire": cls.FIRE_DAMAGE,
            "threads": cls.THREAD_DAMAGE,
            "markings": cls.ILLEGIBLE_MARKING,
        }
        if cleaned in aliases:
            return aliases[cleaned]
        try:
            return cls(cleaned)
        except ValueError as exc:
            raise ValidationError(f"unknown defect {text!r}") from exc


def parse_thousandths(text: str) -> int:
    """Read a depth in inches into thousandths, which is how it is measured."""
    match = _LENGTH.match(text.strip())
    if match is None:
        raise ValidationError(f"a depth is inches to three places, got {text!r}")
    whole: str = match.group("whole")
    frac: str = (match.group("frac") or "").ljust(3, "0")
    return int(whole) * 1000 + int(frac)


@dataclass(frozen=True)
class Observation:
    """One condition, as measured."""

    kind: DefectKind
    depth_thousandths_in: int | None = None
    length_thousandths_in: int | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.depth_thousandths_in is not None and self.depth_thousandths_in <= 0:
            raise ValidationError(f"{self.kind.label} was recorded with a depth of zero or less")
        if self.length_thousandths_in is not None and self.length_thousandths_in <= 0:
            raise ValidationError(f"{self.kind.label} was recorded with a length of zero or less")
        if self.kind.is_measured_by_depth and self.depth_thousandths_in is None:
            raise ValidationError(f"{self.kind.label} has to be measured, not just noted")
        if not self.kind.is_measured_by_depth and self.depth_thousandths_in is not None:
            raise ValidationError(f"{self.kind.label} is not something a depth gauge reads")

    @property
    def depth(self) -> int:
        if self.depth_thousandths_in is None:
            raise ValidationError(f"{self.kind.label} carries no depth")
        return self.depth_thousandths_in

    def describe(self) -> str:
        parts = [self.kind.label]
        if self.depth_thousandths_in is not None:
            parts.append(f"{self.depth_thousandths_in / 1000:.3f} in deep")
        if self.length_thousandths_in is not None:
            parts.append(f"{self.length_thousandths_in / 1000:.3f} in long")
        if self.note:
            parts.append(self.note)
        return ", ".join(parts)
