"""How a cylinder is requalified.

The method is not a preference. It decides which measurements the record of
test must carry, and a record that carries the wrong ones is not a record at
all. Everything downstream branches on this enum rather than on the presence
or absence of a reading.
"""

from __future__ import annotations

from enum import Enum

from starstamp.errors import ValidationError


class Method(Enum):
    """The requalification methods this shop is set up to perform."""

    VOLUMETRIC = "volumetric"
    DIRECT_EXPANSION = "direct_expansion"
    PROOF_PRESSURE = "proof_pressure"
    EXTERNAL_VISUAL = "external_visual"
    ULTRASONIC = "ultrasonic"
    ACETYLENE_VISUAL = "acetylene_visual"

    @property
    def is_pressure_test(self) -> bool:
        """Whether the cylinder gets pumped up at all."""
        return self in {Method.VOLUMETRIC, Method.DIRECT_EXPANSION, Method.PROOF_PRESSURE}

    @property
    def measures_expansion(self) -> bool:
        """Whether total and permanent expansion are part of the record.

        This is the fork the rest of the package turns on. A proof pressure
        test is a pressure test with no expansion reading, so the marked
        rejection elastic expansion is not a criterion for it, and asking for
        one is a category error rather than a missing value.
        """
        return self in {Method.VOLUMETRIC, Method.DIRECT_EXPANSION}

    @property
    def needs_water_jacket(self) -> bool:
        return self is Method.VOLUMETRIC

    @property
    def label(self) -> str:
        return self.value.replace("_", " ")

    @classmethod
    def parse(cls, text: str) -> Method:
        cleaned = text.strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "water_jacket": cls.VOLUMETRIC,
            "wj": cls.VOLUMETRIC,
            "volumetric_expansion": cls.VOLUMETRIC,
            "de": cls.DIRECT_EXPANSION,
            "proof": cls.PROOF_PRESSURE,
            "visual": cls.EXTERNAL_VISUAL,
            "ut": cls.ULTRASONIC,
            "acetylene": cls.ACETYLENE_VISUAL,
        }
        if cleaned in aliases:
            return aliases[cleaned]
        try:
            return cls(cleaned)
        except ValueError as exc:
            known = ", ".join(item.value for item in cls)
            raise ValidationError(f"unknown method {text!r}; the shop performs {known}") from exc
