"""What comes off the rig when a cylinder is pressurised.

The readings are recorded exactly as the operator read them and are never
adjusted here. A shop that rounds a permanent expansion before storing it has
thrown away the only evidence it has that a borderline cylinder was borderline.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from starstamp.errors import ValidationError
from starstamp.model.method import Method
from starstamp.model.units import Expansion, Pressure

MINIMUM_HOLD_SECONDS = 30


@dataclass(frozen=True)
class PressureReadings:
    """One cylinder's turn on the rig.

    Total and permanent expansion are optional because a proof pressure test
    produces neither. They are not defaulted to zero: zero is a reading, and a
    method that takes no reading has to be distinguishable from a cylinder
    that did not move.
    """

    applied: Pressure
    hold_seconds: int
    total_expansion: Expansion | None = None
    permanent_expansion: Expansion | None = None
    leaked: bool = False
    distorted: bool = False

    def __post_init__(self) -> None:
        if self.hold_seconds < 0:
            raise ValidationError("a hold time cannot be negative")
        if (self.total_expansion is None) != (self.permanent_expansion is None):
            raise ValidationError("total and permanent expansion are read together or not at all")
        if self.total_expansion is not None and self.permanent_expansion is not None:
            if self.permanent_expansion > self.total_expansion:
                raise ValidationError(
                    f"permanent expansion {self.permanent_expansion} is more than the total "
                    f"{self.total_expansion}, so the readings are transposed"
                )
            if self.total_expansion.tenths_cc == 0:
                raise ValidationError("a total expansion of zero is not a reading from a rig")

    @property
    def has_expansion(self) -> bool:
        return self.total_expansion is not None

    @property
    def total(self) -> Expansion:
        if self.total_expansion is None:
            raise ValidationError("these readings carry no total expansion")
        return self.total_expansion

    @property
    def permanent(self) -> Expansion:
        if self.permanent_expansion is None:
            raise ValidationError("these readings carry no permanent expansion")
        return self.permanent_expansion

    @property
    def elastic(self) -> Expansion:
        """Total less permanent, which is what the marked limit is about."""
        return Expansion(self.total.tenths_cc - self.permanent.tenths_cc)

    @property
    def permanent_percentage(self) -> Fraction:
        """Permanent expansion as an exact percentage of total."""
        return self.permanent.ratio_to(self.total) * 100

    @property
    def held_long_enough(self) -> bool:
        return self.hold_seconds >= MINIMUM_HOLD_SECONDS

    def suits(self, method: Method) -> bool:
        """Whether these readings are the shape the method calls for."""
        if method.measures_expansion:
            return self.has_expansion
        return not self.has_expansion

    def require_for(self, method: Method) -> PressureReadings:
        if not method.is_pressure_test:
            raise ValidationError(f"{method.label} does not put the cylinder on a rig")
        if method.measures_expansion and not self.has_expansion:
            raise ValidationError(f"{method.label} needs total and permanent expansion")
        if not method.measures_expansion and self.has_expansion:
            raise ValidationError(
                f"{method.label} records no expansion, so these readings belong to another method"
            )
        return self

    def describe(self) -> str:
        parts = [f"{self.applied}", f"held {self.hold_seconds}s"]
        if self.has_expansion:
            parts.append(f"total {self.total}")
            parts.append(f"permanent {self.permanent}")
        if self.leaked:
            parts.append("leaked")
        if self.distorted:
            parts.append("visibly distorted")
        return ", ".join(parts)
