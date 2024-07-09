"""What the shop got through, and what it condemned doing it.

The condemn rate is the number the owner of the shop watches and the number an
auditor asks about, and it is easy to compute wrongly. A rate over every record
counts a suspended cylinder as a survivor and counts a reversed record twice.
So the denominator here is standing records that reached a verdict, and both
halves of that are deliberate.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.model.dates import StampedMonth
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.method import Method
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.text.table import render_table


@dataclass(frozen=True)
class Tally:
    """Counts for one bucket, plus the rate that comes out of them."""

    label: str
    passed: int = 0
    condemned: int = 0
    suspended: int = 0

    @property
    def decided(self) -> int:
        """Records that reached a verdict. A suspension is not one."""
        return self.passed + self.condemned

    @property
    def total(self) -> int:
        return self.decided + self.suspended

    @property
    def condemn_rate(self) -> Fraction:
        if self.decided == 0:
            return Fraction(0)
        return Fraction(self.condemned, self.decided) * 100

    def plus(self, outcome: Outcome) -> Tally:
        from dataclasses import replace

        if outcome is Outcome.PASS:
            return replace(self, passed=self.passed + 1)
        if outcome is Outcome.CONDEMN:
            return replace(self, condemned=self.condemned + 1)
        return replace(self, suspended=self.suspended + 1)

    def row(self) -> list[str]:
        return [
            self.label,
            str(self.passed),
            str(self.condemned),
            str(self.suspended),
            f"{float(self.condemn_rate):.1f}%",
        ]


def standing_between(book: Book, first: date, last: date) -> list[RequalificationEvent]:
    """Every standing record in a window. A reversal counts for nothing here."""
    found = EventRepository(book.connection).between(first, last)
    return [event for event in found if event.state.stands]


def by_month(events: list[RequalificationEvent]) -> list[Tally]:
    buckets: dict[str, Tally] = {}
    for event in events:
        label = StampedMonth.of(event.performed_on).long_form()
        buckets[label] = buckets.get(label, Tally(label)).plus(event.outcome)
    return [buckets[label] for label in sorted(buckets)]


def by_method(events: list[RequalificationEvent]) -> list[Tally]:
    buckets: dict[str, Tally] = {}
    for event in events:
        label = event.method.label
        buckets[label] = buckets.get(label, Tally(label)).plus(event.outcome)
    return [buckets[label] for label in sorted(buckets)]


def by_technician(events: list[RequalificationEvent]) -> list[Tally]:
    buckets: dict[str, Tally] = {}
    for event in events:
        label = event.technician_badge
        buckets[label] = buckets.get(label, Tally(label)).plus(event.outcome)
    return [buckets[label] for label in sorted(buckets)]


def overall(events: list[RequalificationEvent]) -> Tally:
    tally = Tally("all")
    for event in events:
        tally = tally.plus(event.outcome)
    return tally


def condemning_reasons(events: list[RequalificationEvent]) -> list[tuple[str, int]]:
    """The reasons cylinders were condemned, commonest first."""
    counter: Counter[str] = Counter()
    for event in events:
        if event.outcome is Outcome.CONDEMN:
            for reason in event.reasons:
                counter[reason.split(",")[0]] += 1
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def starred_share(events: list[RequalificationEvent]) -> Fraction:
    """What share of the passes earned a star."""
    passes = [event for event in events if event.outcome is Outcome.PASS]
    if not passes:
        return Fraction(0)
    starred = sum(1 for event in passes if event.starred)
    return Fraction(starred, len(passes)) * 100


def render(tallies: list[Tally], heading: str) -> str:
    if not tallies:
        return f"{heading}: nothing in the window"
    return render_table(
        [heading, "pass", "condemn", "suspend", "rate"],
        [tally.row() for tally in tallies],
        right=(1, 2, 3, 4),
    )


def render_summary(events: list[RequalificationEvent]) -> str:
    tally = overall(events)
    lines = [
        f"{tally.total} records, {tally.passed} passed, {tally.condemned} condemned, "
        f"{tally.suspended} suspended",
        f"condemn rate {float(tally.condemn_rate):.1f}% of the {tally.decided} that reached a "
        "verdict",
        f"{float(starred_share(events)):.1f}% of passes earned a star",
    ]
    reasons = condemning_reasons(events)
    if reasons:
        lines.append("condemned for:")
        lines.extend(f"  {count} x {reason}" for reason, count in reasons)
    methods = {event.method for event in events}
    if methods:
        lines.append("methods used: " + ", ".join(sorted(m.label for m in methods)))
    return "\n".join(lines)


def unused_methods(events: list[RequalificationEvent]) -> frozenset[Method]:
    return frozenset(Method) - frozenset(event.method for event in events)
