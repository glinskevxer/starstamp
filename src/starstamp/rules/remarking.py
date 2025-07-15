"""Whether a cylinder may be re-marked, and from what.

The rule that matters is about evidence rather than about skill. A requalifier
may restore a mark it can show was there; it may not decide what a cylinder is.
So the shop's own records are the best evidence, an owner's declaration is
weaker and is not enough on its own for the marks that say what the cylinder
is, and nothing at all is never enough.

The identity marks are the sharp case. Restoring a serial from the shop's own
record of test is restoring; restoring one from a customer's say so is
inventing a cylinder, and the shop that does it has made two cylinders with
the same serial somewhere in the country.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import Cylinder
from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.marking import Evidence, MarkKind, RestoredMark

CITATION = "49 CFR 180.213"


@dataclass(frozen=True)
class RemarkingCheck:
    """Whether the shop may restore these marks, and why not."""

    refusals: tuple[str, ...]

    @property
    def allowed(self) -> bool:
        return not self.refusals

    def require(self) -> RemarkingCheck:
        if self.allowed:
            return self
        raise RuleViolationError("; ".join(self.refusals), CITATION)


def supporting_records(history: list[RequalificationEvent]) -> list[RequalificationEvent]:
    """The records that could stand behind a re-marking."""
    return [event for event in history if event.state.stands and event.outcome is Outcome.PASS]


def check(
    cylinder: Cylinder,
    marks: tuple[RestoredMark, ...],
    evidence: Evidence,
    history: list[RequalificationEvent],
    day: date,
) -> RemarkingCheck:
    """Judge one proposed re-marking."""
    refusals: list[str] = []
    if cylinder.status.is_terminal:
        refusals.append(f"{cylinder.key} is {cylinder.status.value} and is not re-marked")

    identity = [mark for mark in marks if mark.kind.is_identity]
    supporting = supporting_records(history)

    if evidence is Evidence.OUR_RECORDS and not supporting:
        refusals.append(
            f"{cylinder.key} has no standing record of test here to restore a mark from"
        )
    if identity and evidence is Evidence.OWNER_DECLARATION:
        names = ", ".join(sorted(mark.kind.label for mark in identity))
        refusals.append(
            f"an owner's declaration is not evidence for the {names}; "
            "that has to come from our records or the maker"
        )
    restoring_spec = any(mark.kind is MarkKind.SPECIFICATION for mark in marks)
    from_the_maker = evidence is Evidence.MANUFACTURER_LETTER
    if restoring_spec and not from_the_maker and not supporting:
        refusals.append("restoring a specification needs the maker's letter or a record of ours")
    for mark in marks:
        if mark.kind is MarkKind.SERIAL and mark.reads != cylinder.key.serial:
            refusals.append(
                f"the serial on the book is {cylinder.key.serial} and the mark reads "
                f"{mark.reads}; a re-marking restores, it does not rename"
            )
        if mark.kind is MarkKind.MANUFACTURER and mark.reads != (cylinder.key.manufacturer_symbol):
            refusals.append(
                f"the maker on the book is {cylinder.key.manufacturer_symbol} and the mark "
                f"reads {mark.reads}"
            )
    if supporting and supporting[-1].performed_on > day:
        refusals.append("the record it rests on is dated after the re-marking")
    return RemarkingCheck(tuple(refusals))
