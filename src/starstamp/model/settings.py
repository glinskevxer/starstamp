"""The handful of numbers a shop is allowed to set for itself.

Most of what this package does is fixed by regulation and none of that belongs
here. What does belong here is the shop's own arrangements: how much one rig
gets through in a day, how tight it holds its start of day check, how long it
holds a cylinder before it charges storage. Each one is dated, because
changing a tolerance today must not change what last year's tests meant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.errors import NotFoundError, ValidationError

CAPACITY_PER_RIG = "capacity_per_rig"
CHECK_TOLERANCE = "check_tolerance_percent"
MINIMUM_HOLD = "minimum_hold_seconds"
STORAGE_FREE_DAYS = "storage_free_days"

DEFAULTS: dict[str, str] = {
    CAPACITY_PER_RIG: "24",
    CHECK_TOLERANCE: "1",
    MINIMUM_HOLD: "30",
    STORAGE_FREE_DAYS: "30",
}

_LIMITS: dict[str, tuple[int, int]] = {
    CAPACITY_PER_RIG: (1, 500),
    CHECK_TOLERANCE: (1, 100),
    MINIMUM_HOLD: (30, 600),
    STORAGE_FREE_DAYS: (0, 365),
}


def known_settings() -> list[str]:
    return sorted(DEFAULTS)


def check_value(name: str, value: str) -> str:
    """Check a setting before it goes anywhere near the book."""
    if name not in DEFAULTS:
        raise ValidationError(
            f"unknown setting {name!r}; the shop sets {', '.join(known_settings())}"
        )
    cleaned = value.strip()
    if name == CHECK_TOLERANCE:
        try:
            tolerance = Fraction(cleaned)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValidationError(f"{name} is a number, got {value!r}") from exc
        if not 0 < tolerance <= 100:
            raise ValidationError(f"{name} runs above zero and up to 100, got {cleaned}")
        return cleaned
    if not cleaned.isdigit():
        raise ValidationError(f"{name} is a whole number, got {value!r}")
    low, high = _LIMITS[name]
    number = int(cleaned)
    if not low <= number <= high:
        raise ValidationError(f"{name} runs from {low} to {high}, got {number}")
    return cleaned


@dataclass(frozen=True)
class Setting:
    """One value the shop set, from a day."""

    name: str
    value: str
    effective_from: date

    def __post_init__(self) -> None:
        check_value(self.name, self.value)

    def applies_on(self, day: date) -> bool:
        return day >= self.effective_from

    def as_int(self) -> int:
        return int(Fraction(self.value))

    def as_fraction(self) -> Fraction:
        return Fraction(self.value)

    def __str__(self) -> str:
        return f"{self.name} = {self.value} from {self.effective_from}"


@dataclass(frozen=True)
class Settings:
    """Every setting the shop has ever had, read for a day."""

    entries: tuple[Setting, ...] = ()

    def on(self, name: str, day: date) -> Setting:
        if name not in DEFAULTS:
            raise NotFoundError(f"no such setting {name!r}")
        candidates = [
            entry for entry in self.entries if entry.name == name and entry.applies_on(day)
        ]
        if not candidates:
            return Setting(name, DEFAULTS[name], date(1900, 1, 1))
        return max(candidates, key=lambda entry: entry.effective_from)

    def integer(self, name: str, day: date) -> int:
        return self.on(name, day).as_int()

    def fraction(self, name: str, day: date) -> Fraction:
        return self.on(name, day).as_fraction()

    def current(self, day: date) -> dict[str, str]:
        return {name: self.on(name, day).value for name in known_settings()}
