"""What an acetylene cylinder's examination records.

An acetylene cylinder is not a pressure vessel with gas in it. It is a shell
packed with a porous mass, soaked in acetone, with the gas dissolved in the
acetone. None of that can be pressure tested, so the examination is a weighing
and a look: the mass and the acetone together are most of the cylinder's tare
weight, and a cylinder that has lost weight has lost acetone, which leaves gas
pockets where there should be none.
"""

from __future__ import annotations

from dataclasses import dataclass

from starstamp.errors import ValidationError


@dataclass(frozen=True)
class AcetyleneExam:
    """One acetylene cylinder on the scale and under the light."""

    tare_now_hundredths_lb: int
    fuse_plugs_sound: bool = True
    mass_settled: bool = False
    shell_sound: bool = True
    cap_sound: bool = True
    note: str | None = None

    def __post_init__(self) -> None:
        if self.tare_now_hundredths_lb <= 0:
            raise ValidationError("a tare weight of zero is not a weighing")

    def loss_against(self, marked_hundredths_lb: int) -> int:
        """How much lighter it is than its marked tare, in hundredths of a pound.

        Negative when the cylinder weighs more than its mark, which happens
        and usually means water in it rather than a heavy mass.
        """
        return marked_hundredths_lb - self.tare_now_hundredths_lb

    def describe(self) -> str:
        parts = [f"tare {self.tare_now_hundredths_lb / 100:.2f} lb"]
        if not self.fuse_plugs_sound:
            parts.append("fuse plugs unsound")
        if self.mass_settled:
            parts.append("mass settled")
        if not self.shell_sound:
            parts.append("shell unsound")
        if not self.cap_sound:
            parts.append("cap unsound")
        if self.note:
            parts.append(self.note)
        return ", ".join(parts)
