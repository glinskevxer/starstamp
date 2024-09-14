"""How a test system is doing, read off its own paperwork.

Two questions the shop asks about a rig and one it should. It asks what is
about to expire and how much work the rig is getting. It should ask how the
start of day checks are trending, because a jacket going out does not fail its
check one morning: it drifts for a fortnight first, inside tolerance the whole
way, and then a batch of cylinders reads two percent low.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from starstamp.model.calibration import Certificate, SystemCheck
from starstamp.model.event import Outcome
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.text.table import render_table


@dataclass(frozen=True)
class RigStanding:
    """One rig, its certificates and what it got through."""

    system_code: str
    certificates: tuple[Certificate, ...]
    checks: tuple[SystemCheck, ...]
    tested: int
    condemned: int

    def expiring_within(self, day: date, days: int) -> list[Certificate]:
        return [
            certificate
            for certificate in self.certificates
            if 0 <= certificate.days_left(day) <= days
        ]

    def expired_on(self, day: date) -> list[Certificate]:
        return [certificate for certificate in self.certificates if certificate.days_left(day) < 0]

    @property
    def checks_run(self) -> int:
        return len(self.checks)

    @property
    def failed_checks(self) -> tuple[SystemCheck, ...]:
        return tuple(check for check in self.checks if not check.within_tolerance)

    def drift(self) -> Fraction:
        """The average signed deviation across the checks in the window.

        A rig that reads high half the time and low the other half averages to
        nothing, which is what a healthy jacket looks like. A rig drifting one
        way shows up here long before any single check fails.
        """
        if not self.checks:
            return Fraction(0)
        return sum((check.deviation for check in self.checks), Fraction(0)) / len(self.checks)

    def describe(self, day: date) -> str:
        lines = [
            f"{self.system_code}: {self.tested} tested, {self.condemned} condemned, "
            f"{self.checks_run} start of day checks"
        ]
        if self.checks:
            lines.append(f"  drift {float(self.drift()):+.2f}% on average")
        for check in self.failed_checks:
            lines.append(f"  out of tolerance: {check.describe()}")
        for certificate in self.expired_on(day):
            lines.append(
                f"  EXPIRED: {certificate.instrument} {certificate.serial} on "
                f"{certificate.valid_until.isoformat()}"
            )
        for certificate in self.expiring_within(day, 90):
            lines.append(
                f"  due: {certificate.instrument} {certificate.serial} in "
                f"{certificate.days_left(day)} days"
            )
        return "\n".join(lines)


def build(book: Book, system_code: str, first: date, last: date) -> RigStanding:
    calibration = CalibrationRepository(book.connection)
    events = EventRepository(book.connection)
    standing = [
        event for event in events.for_system_between(system_code, first, last) if event.state.stands
    ]
    return RigStanding(
        system_code=system_code,
        certificates=tuple(calibration.certificates(system_code)),
        checks=tuple(calibration.checks_between(system_code, first, last)),
        tested=len(standing),
        condemned=sum(1 for event in standing if event.outcome is Outcome.CONDEMN),
    )


def build_all(book: Book, first: date, last: date) -> list[RigStanding]:
    calibration = CalibrationRepository(book.connection)
    return [build(book, code, first, last) for code in calibration.systems()]


def render(standings: list[RigStanding], day: date) -> str:
    if not standings:
        return "no test systems on file"
    table = render_table(
        ["system", "certificates", "checks", "failed", "tested", "condemned", "drift"],
        [
            [
                standing.system_code,
                str(len(standing.certificates)),
                str(standing.checks_run),
                str(len(standing.failed_checks)),
                str(standing.tested),
                str(standing.condemned),
                f"{float(standing.drift()):+.2f}%",
            ]
            for standing in standings
        ],
        right=(1, 2, 3, 4, 5, 6),
    )
    notes = [standing.describe(day) for standing in standings]
    return table + "\n\n" + "\n".join(notes)
