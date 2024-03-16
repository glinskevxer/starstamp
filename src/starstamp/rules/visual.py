"""Turning what the inspector measured into a verdict.

The limits are fractions of the cylinder's nominal wall, so nothing here can
be decided without knowing the wall. That is deliberate: the same sixteen
thousandth pit is nothing on a heavy walled 3AA and most of the way through a
thin walled 4BA, and a shop that carries one table of absolute depths will
condemn good cylinders and pass bad ones.

Two of the rules read another measurement to decide which limit applies.
Corrosion in a line is held to a much tighter fraction than a pit, but only
once it runs three inches or more, so its length decides which limit its depth
is compared against. A dent is compared against its own width rather than
against the wall at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from starstamp.errors import RuleViolationError
from starstamp.model.defect import DefectKind, Observation
from starstamp.model.service import GasService
from starstamp.model.specification import SpecFamily, Specification

CITATION = "CGA C-6"
LINE_CORROSION_RUN_THOUSANDTHS = 3000


class VisualResult(Enum):
    """What the bench does with the cylinder next."""

    PASS = "pass"
    REPAIR = "repair"
    CONDEMN = "condemn"

    @property
    def rank(self) -> int:
        return {"pass": 0, "repair": 1, "condemn": 2}[self.value]


_FRACTION_LIMITS: dict[DefectKind, Fraction] = {
    DefectKind.GENERAL_CORROSION: Fraction(1, 10),
    DefectKind.INTERIOR_CORROSION: Fraction(1, 10),
    DefectKind.ISOLATED_PITTING: Fraction(1, 5),
    DefectKind.LINE_CORROSION: Fraction(1, 20),
    DefectKind.CREVICE_CORROSION: Fraction(1, 20),
    DefectKind.CUT_GOUGE_DIG: Fraction(1, 10),
}

_ALWAYS_CONDEMNED = {
    DefectKind.CRACK,
    DefectKind.BULGE,
    DefectKind.LEAK,
    DefectKind.ARC_BURN,
    DefectKind.TORCH_BURN,
}

_REPAIRABLE = {
    DefectKind.NECK_DAMAGE,
    DefectKind.THREAD_DAMAGE,
    DefectKind.ILLEGIBLE_MARKING,
    DefectKind.FOOTRING_DAMAGE,
}

_HEAT_TREATABLE = {SpecFamily.SEAMLESS_STEEL, SpecFamily.WELDED_STEEL}


@dataclass(frozen=True)
class Finding:
    """One observation, judged."""

    observation: Observation
    result: VisualResult
    reason: str

    def __str__(self) -> str:
        return f"{self.result.value}: {self.observation.describe()} ({self.reason})"


@dataclass(frozen=True)
class VisualAssessment:
    """Every finding, and the worst of them."""

    findings: tuple[Finding, ...]

    @property
    def result(self) -> VisualResult:
        if not self.findings:
            return VisualResult.PASS
        return max((finding.result for finding in self.findings), key=lambda item: item.rank)

    @property
    def condemned(self) -> bool:
        return self.result is VisualResult.CONDEMN

    @property
    def passes(self) -> bool:
        return self.result is VisualResult.PASS

    def condemning(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.result is VisualResult.CONDEMN)


def limit_for(observation: Observation) -> Fraction:
    """The fraction of wall this observation's depth is held to.

    Line and crevice corrosion only earn the tight limit once they run three
    inches. Shorter than that the shop treats the reading as a pit, which is
    the same decision CGA C-6 makes and the reason a length is recorded at all.
    """
    kind = observation.kind
    if kind in {DefectKind.LINE_CORROSION, DefectKind.CREVICE_CORROSION}:
        length = observation.length_thousandths_in
        if length is None:
            raise RuleViolationError(f"{kind.label} cannot be judged without its length", CITATION)
        if length < LINE_CORROSION_RUN_THOUSANDTHS:
            return _FRACTION_LIMITS[DefectKind.ISOLATED_PITTING]
    limit = _FRACTION_LIMITS.get(kind)
    if limit is None:
        raise RuleViolationError(f"{kind.label} is not judged against the wall", CITATION)
    return limit


def _judge_dent(observation: Observation) -> Finding:
    """A dent is judged against its own width, never against the wall."""
    width = observation.length_thousandths_in
    if width is None:
        raise RuleViolationError("a dent cannot be judged without its width", CITATION)
    if observation.depth * 10 > width:
        return Finding(
            observation,
            VisualResult.CONDEMN,
            f"deeper than a tenth of its {width / 1000:.3f} in width",
        )
    return Finding(observation, VisualResult.PASS, "within a tenth of its width")


def _judge_fire(observation: Observation, specification: Specification) -> Finding:
    """Fire damage ends a light alloy cylinder and only suspends a steel one."""
    if specification.family in _HEAT_TREATABLE:
        return Finding(
            observation,
            VisualResult.REPAIR,
            "steel, so it may go out for heat treatment before requalification",
        )
    return Finding(
        observation,
        VisualResult.CONDEMN,
        f"{specification.family.value} is not heat treated back into service",
    )


def judge(
    observation: Observation, specification: Specification, wall_thousandths_in: int
) -> Finding:
    """Judge one observation against the cylinder it was found on."""
    kind = observation.kind
    if kind in _ALWAYS_CONDEMNED:
        return Finding(observation, VisualResult.CONDEMN, "condemned on sight")
    if kind is DefectKind.FIRE_DAMAGE:
        return _judge_fire(observation, specification)
    if kind in _REPAIRABLE:
        return Finding(observation, VisualResult.REPAIR, "put right before the cylinder ships")
    if kind is DefectKind.DENT:
        return _judge_dent(observation)
    if wall_thousandths_in <= 0:
        raise RuleViolationError(
            f"{kind.label} cannot be judged without the cylinder's wall thickness", CITATION
        )
    limit = limit_for(observation)
    allowed = Fraction(wall_thousandths_in) * limit
    if Fraction(observation.depth) > allowed:
        return Finding(
            observation,
            VisualResult.CONDEMN,
            f"deeper than {limit} of the {wall_thousandths_in / 1000:.3f} in wall",
        )
    return Finding(observation, VisualResult.PASS, f"within {limit} of the wall")


def assess(
    observations: list[Observation],
    specification: Specification,
    service: GasService,
    wall_thousandths_in: int,
) -> VisualAssessment:
    """Judge everything the inspector wrote down.

    The gas matters here only once: a cylinder in a service that rusts from the
    inside has to have been looked at from the inside, and an inspection that
    never records an interior reading for one of those is incomplete rather
    than passing.
    """
    findings = [
        judge(observation, specification, wall_thousandths_in) for observation in observations
    ]
    if service.needs_interior_inspection:
        looked_inside = any(
            observation.kind is DefectKind.INTERIOR_CORROSION for observation in observations
        )
        if not looked_inside:
            raise RuleViolationError(
                f"a cylinder in {service} has to be inspected internally before it passes",
                CITATION,
            )
    return VisualAssessment(tuple(findings))
