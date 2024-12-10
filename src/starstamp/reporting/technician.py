"""What each person on the bench got through, and how their work compares.

The comparison is the point and it needs care. A technician whose condemn rate
is far below everybody else's is either luckier than the rest or is passing
cylinders the others would fail, and the shop cannot tell which from this
report. What it can do is say which way the difference runs and how much work
it rests on, so that nobody reads a two point spread across nine cylinders as
a finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.method import Method
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.store.facility import TechnicianRepository
from starstamp.text.table import render_table

ENOUGH_TO_COMPARE = 20
NOTABLE_SPREAD = Fraction(10)


@dataclass(frozen=True)
class Workload:
    """One technician's window."""

    badge: str
    name: str
    events: tuple[RequalificationEvent, ...]

    @property
    def performed(self) -> int:
        return len(self.events)

    @property
    def condemned(self) -> int:
        return sum(1 for event in self.events if event.outcome is Outcome.CONDEMN)

    @property
    def decided(self) -> int:
        return sum(1 for event in self.events if event.outcome in {Outcome.PASS, Outcome.CONDEMN})

    @property
    def starred(self) -> int:
        return sum(1 for event in self.events if event.starred)

    def condemn_rate(self) -> Fraction:
        if self.decided == 0:
            return Fraction(0)
        return Fraction(self.condemned, self.decided) * 100

    def methods(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in self.events:
            counts[event.method.label] = counts.get(event.method.label, 0) + 1
        return dict(sorted(counts.items()))

    def busiest_day(self) -> tuple[date, int] | None:
        if not self.events:
            return None
        counts: dict[date, int] = {}
        for event in self.events:
            counts[event.performed_on] = counts.get(event.performed_on, 0) + 1
        day = max(counts, key=lambda item: (counts[item], item))
        return day, counts[day]

    def row(self) -> list[str]:
        return [
            self.badge,
            self.name,
            str(self.performed),
            str(self.condemned),
            str(self.starred),
            f"{float(self.condemn_rate()):.1f}%",
        ]


@dataclass(frozen=True)
class Comparison:
    """Everybody's window, and who sits away from the middle."""

    workloads: tuple[Workload, ...]

    @property
    def total_decided(self) -> int:
        return sum(item.decided for item in self.workloads)

    def shop_rate(self) -> Fraction:
        decided = self.total_decided
        if decided == 0:
            return Fraction(0)
        condemned = sum(item.condemned for item in self.workloads)
        return Fraction(condemned, decided) * 100

    def outliers(self) -> tuple[tuple[Workload, Fraction], ...]:
        """Technicians far from the shop rate, on enough work to mean it."""
        shop = self.shop_rate()
        found = []
        for workload in self.workloads:
            if workload.decided < ENOUGH_TO_COMPARE:
                continue
            spread = workload.condemn_rate() - shop
            if abs(spread) >= NOTABLE_SPREAD:
                found.append((workload, spread))
        return tuple(found)

    def describe(self) -> str:
        if not self.workloads:
            return "nobody did any work in that window"
        lines = [
            f"{len(self.workloads)} on the bench, {self.total_decided} cylinders decided, "
            f"shop condemn rate {float(self.shop_rate()):.1f}%"
        ]
        for workload, spread in self.outliers():
            direction = "above" if spread > 0 else "below"
            lines.append(
                f"  {workload.badge} is {abs(float(spread)):.1f} points {direction} the shop "
                f"rate on {workload.decided} cylinders"
            )
        return "\n".join(lines)


def build(book: Book, first: date, last: date) -> Comparison:
    events = EventRepository(book.connection)
    technicians = {item.badge: item.name for item in TechnicianRepository(book.connection).all()}
    grouped: dict[str, list[RequalificationEvent]] = {}
    for event in events.between(first, last):
        if not event.state.stands:
            continue
        grouped.setdefault(event.technician_badge, []).append(event)
    workloads = [
        Workload(badge, technicians.get(badge, "off the bench"), tuple(found))
        for badge, found in sorted(grouped.items())
    ]
    return Comparison(tuple(workloads))


def render(comparison: Comparison) -> str:
    if not comparison.workloads:
        return comparison.describe()
    table = render_table(
        ["badge", "name", "done", "condemned", "starred", "rate"],
        [workload.row() for workload in comparison.workloads],
        right=(2, 3, 4, 5),
    )
    return f"{table}\n\n{comparison.describe()}"


def method_mix(comparison: Comparison) -> dict[str, int]:
    counts: dict[str, int] = {}
    for workload in comparison.workloads:
        for label, count in workload.methods().items():
            counts[label] = counts.get(label, 0) + count
    return dict(sorted(counts.items()))


def unused_by(workload: Workload) -> frozenset[Method]:
    return frozenset(Method) - frozenset(event.method for event in workload.events)
