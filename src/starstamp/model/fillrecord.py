"""What actually went into a cylinder.

A filling record is not a requalification and the shop is not required to keep
one, which is exactly why it is worth keeping: the cylinders that come back
condemned are disproportionately the ones somebody filled hot and topped up
cold, and without a fill log there is no way to show that.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.errors import ValidationError
from starstamp.model.service import GasService
from starstamp.model.units import Pressure

ABSOLUTE_ZERO_OFFSET = 460
REFERENCE_TEMPERATURE_F = 70


@dataclass(frozen=True)
class FillRecord:
    """One fill, as the plant recorded it."""

    cylinder_key: str
    service: GasService
    filled_on: date
    filler_badge: str
    pressure: Pressure | None = None
    weight_hundredths_lb: int | None = None
    temperature_f: int = REFERENCE_TEMPERATURE_F
    note: str | None = None
    fill_id: int | None = None

    def __post_init__(self) -> None:
        if (self.pressure is None) == (self.weight_hundredths_lb is None):
            raise ValidationError(
                "a fill is measured by pressure or by weight, and it has to be one of them"
            )
        if self.weight_hundredths_lb is not None and self.weight_hundredths_lb <= 0:
            raise ValidationError("a fill weight of zero is not a fill")
        if not -60 <= self.temperature_f <= 160:
            raise ValidationError(
                f"a filling temperature of {self.temperature_f}F is not a reading"
            )
        if self.service.liquefied and self.pressure is not None:
            raise ValidationError(f"{self.service} is filled by weight, not to a pressure")
        if not self.service.liquefied and self.weight_hundredths_lb is not None:
            raise ValidationError(f"{self.service} is filled to a pressure, not by weight")

    @property
    def is_by_weight(self) -> bool:
        return self.weight_hundredths_lb is not None

    def settled_pressure(self) -> Pressure:
        """The pressure this fill will read once the cylinder cools to seventy.

        A cylinder filled fast is warm, and a warm cylinder reads high. The
        correction is the ratio of absolute temperatures, which is the whole
        of the arithmetic and the part every plant gets wrong by leaving it
        out.
        """
        if self.pressure is None:
            raise ValidationError("a fill by weight has no settled pressure")
        factor = Fraction(
            REFERENCE_TEMPERATURE_F + ABSOLUTE_ZERO_OFFSET,
            self.temperature_f + ABSOLUTE_ZERO_OFFSET,
        )
        return self.pressure.scaled(factor)

    def describe(self) -> str:
        if self.is_by_weight:
            weight = (self.weight_hundredths_lb or 0) / 100
            head = f"{weight:.2f} lb"
        else:
            head = f"{self.pressure} at {self.temperature_f}F"
            if self.temperature_f != REFERENCE_TEMPERATURE_F:
                head = f"{head}, {self.settled_pressure()} settled"
        line = f"{self.filled_on.isoformat()} {self.cylinder_key} {self.service} {head}"
        if self.note:
            line = f"{line} ({self.note})"
        return line
