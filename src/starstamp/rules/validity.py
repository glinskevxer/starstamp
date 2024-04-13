"""Whether a set of readings counts as a requalification at all.

This is the rule that decides what the other rules are allowed to look at. A
permanent expansion of eight percent is a pass under a calibrated rig and
nothing at all under a rig whose certificate lapsed the week before, and the
numbers are identical in both cases. So validity is settled before any
criterion is applied to a reading, and an invalid event can never carry a
mark no matter how good it looks.

The method decides which instruments have to be in date. A proof pressure test
needs the pressure indicator and nothing else, because it takes no expansion
reading, and holding it to the expansion scale's certificate would fail tests
for want of an instrument they never used.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import RuleViolationError
from starstamp.model.calibration import Certificate, InstrumentKind, SystemCheck
from starstamp.model.method import Method

CITATION = "49 CFR 180.205(g)"

_REQUIRED: dict[Method, frozenset[str]] = {
    Method.VOLUMETRIC: frozenset(
        {
            InstrumentKind.CALIBRATED_CYLINDER,
            InstrumentKind.PRESSURE_INDICATOR,
            InstrumentKind.EXPANSION_SCALE,
        }
    ),
    Method.DIRECT_EXPANSION: frozenset(
        {InstrumentKind.PRESSURE_INDICATOR, InstrumentKind.EXPANSION_SCALE}
    ),
    Method.PROOF_PRESSURE: frozenset({InstrumentKind.PRESSURE_INDICATOR}),
    Method.ULTRASONIC: frozenset({InstrumentKind.THICKNESS_GAUGE}),
    Method.EXTERNAL_VISUAL: frozenset(),
    Method.ACETYLENE_VISUAL: frozenset(),
}

_NEEDS_DAILY_CHECK = {Method.VOLUMETRIC, Method.DIRECT_EXPANSION}


def required_instruments(method: Method) -> frozenset[str]:
    """The instruments whose certificates have to be in date for this method."""
    return _REQUIRED[method]


def needs_daily_check(method: Method) -> bool:
    return method in _NEEDS_DAILY_CHECK


@dataclass(frozen=True)
class Validity:
    """Whether the rig was fit to produce these readings, and why not."""

    method: Method
    day: date
    system_code: str
    faults: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.faults

    def require(self) -> Validity:
        if self.is_valid:
            return self
        raise RuleViolationError(
            f"{self.system_code} was not fit to requalify on {self.day.isoformat()}: "
            + "; ".join(self.faults),
            CITATION,
        )

    def describe(self) -> str:
        if self.is_valid:
            return f"{self.system_code} in calibration on {self.day.isoformat()}"
        return f"{self.system_code} not in calibration: " + "; ".join(self.faults)


def assess(
    method: Method,
    day: date,
    system_code: str,
    certificates: list[Certificate],
    check: SystemCheck | None,
) -> Validity:
    """Judge the rig, reporting every fault rather than the first one.

    An auditor asked to explain a restatement wants the whole reason the
    events were pulled, and a shop fixing a rig wants to fix it once.
    """
    faults: list[str] = []
    held = {
        certificate.instrument: certificate
        for certificate in certificates
        if certificate.system_code == system_code
    }
    for instrument in sorted(required_instruments(method)):
        certificate = held.get(instrument)
        if certificate is None:
            faults.append(f"no {instrument} certificate on file")
        elif not certificate.valid_on(day):
            if day < certificate.issued_on:
                faults.append(
                    f"{instrument} certificate not issued until {certificate.issued_on.isoformat()}"
                )
            else:
                faults.append(
                    f"{instrument} certificate expired {certificate.valid_until.isoformat()}"
                )

    if needs_daily_check(method):
        if check is None:
            faults.append("no start of day check")
        elif check.day != day:
            faults.append(f"start of day check is dated {check.day.isoformat()}")
        elif check.system_code != system_code:
            faults.append(f"start of day check belongs to {check.system_code}")
        elif not check.within_tolerance:
            faults.append(f"start of day check off by {float(check.deviation):.2f}%")

    return Validity(method, day, system_code, tuple(faults))
