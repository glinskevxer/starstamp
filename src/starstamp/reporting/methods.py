"""What the shop actually did, method by method.

The method mix is the shape of a shop. One that runs almost everything through
the water jacket is a shop that requalifies; one whose work is mostly external
visuals is a shop that inspects propane cylinders and should be reading its
capacity and its prices differently.

The numbers beside each method are the ones that differ between them: the
intervals they granted, the stars they made possible, and how often each one
ended in a condemnation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.method import Method
from starstamp.store.db import Book
from starstamp.text.table import render_table

from . import throughput


@dataclass(frozen=True)
class MethodRow:
    """One method over a window."""

    method: Method
    performed: int
    condemned: int
    starred: int
    people: frozenset[str]

    @property
    def condemn_rate(self) -> Fraction:
        if self.performed == 0:
            return Fraction(0)
        return Fraction(self.condemned, self.performed) * 100

    @property
    def star_rate(self) -> Fraction:
        if self.performed == 0:
            return Fraction(0)
        return Fraction(self.starred, self.performed) * 100

    def row(self) -> list[str]:
        return [
            self.method.label,
            str(self.performed),
            str(self.condemned),
            f"{float(self.condemn_rate):.1f}%",
            str(self.starred),
            str(len(self.people)),
        ]


@dataclass(frozen=True)
class MethodMix:
    """Every method, whether it was used or not."""

    first: date
    last: date
    rows: tuple[MethodRow, ...]

    @property
    def used(self) -> tuple[MethodRow, ...]:
        return tuple(row for row in self.rows if row.performed)

    @property
    def unused(self) -> frozenset[Method]:
        return frozenset(row.method for row in self.rows if not row.performed)

    def busiest(self) -> MethodRow | None:
        used = self.used
        if not used:
            return None
        return max(used, key=lambda row: row.performed)

    def describe(self) -> str:
        used = self.used
        if not used:
            return f"nothing was requalified between {self.first} and {self.last}"
        total = sum(row.performed for row in used)
        busiest = self.busiest()
        line = f"{total} cylinders across {len(used)} methods"
        if busiest is not None:
            share = Fraction(busiest.performed, total) * 100
            line = f"{line}; {busiest.method.label} is {float(share):.0f}% of it"
        return line


def build(book: Book, first: date, last: date) -> MethodMix:
    events: list[RequalificationEvent] = throughput.standing_between(book, first, last)
    rows: list[MethodRow] = []
    for method in Method:
        theirs = [event for event in events if event.method is method]
        rows.append(
            MethodRow(
                method=method,
                performed=len(theirs),
                condemned=sum(1 for e in theirs if e.outcome is Outcome.CONDEMN),
                starred=sum(1 for e in theirs if e.starred),
                people=frozenset(e.technician_badge for e in theirs),
            )
        )
    return MethodMix(first, last, tuple(rows))


def render(mix: MethodMix) -> str:
    if not mix.used:
        return mix.describe()
    table = render_table(
        ["method", "done", "condemned", "rate", "starred", "people"],
        [row.row() for row in mix.used],
        right=(1, 2, 3, 4, 5),
    )
    lines = [table, "", mix.describe()]
    if mix.unused:
        lines.append("not used: " + ", ".join(sorted(item.label for item in mix.unused)))
    return "\n".join(lines)
