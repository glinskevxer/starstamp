from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import CylinderStatus
from starstamp.model.event import Outcome
from starstamp.model.marking import Evidence, MarkKind, RestoredMark
from starstamp.rules.remarking import check, supporting_records

from ..support.factories import make_cylinder, make_event

DAY = date(2024, 6, 14)
A_PASS = [make_event(performed_on=date(2024, 6, 12))]


def test_a_mark_restored_from_our_own_record() -> None:
    result = check(
        make_cylinder(),
        (RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),),
        Evidence.OUR_RECORDS,
        A_PASS,
        DAY,
    )
    assert result.allowed
    assert result.require() is result


def test_our_records_have_to_hold_something() -> None:
    result = check(
        make_cylinder(),
        (RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),),
        Evidence.OUR_RECORDS,
        [],
        DAY,
    )
    assert not result.allowed
    assert "no standing record of test here" in result.refusals[0]


def test_an_owners_word_is_not_enough_for_a_serial() -> None:
    result = check(
        make_cylinder(),
        (RestoredMark(MarkKind.SERIAL, "A4471"),),
        Evidence.OWNER_DECLARATION,
        A_PASS,
        DAY,
    )
    assert not result.allowed
    assert "not evidence for the serial" in result.refusals[0]


def test_an_owners_word_is_enough_for_a_tare_weight() -> None:
    assert check(
        make_cylinder(),
        (RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),),
        Evidence.OWNER_DECLARATION,
        [],
        DAY,
    ).allowed


def test_a_specification_needs_the_maker_or_our_records() -> None:
    refused = check(
        make_cylinder(),
        (RestoredMark(MarkKind.SPECIFICATION, "DOT-3AA2015"),),
        Evidence.OWNER_DECLARATION,
        [],
        DAY,
    )
    assert "maker's letter" in refused.refusals[0]
    allowed = check(
        make_cylinder(),
        (RestoredMark(MarkKind.SPECIFICATION, "DOT-3AA2015"),),
        Evidence.MANUFACTURER_LETTER,
        [],
        DAY,
    )
    assert allowed.allowed


def test_a_remarking_restores_and_does_not_rename() -> None:
    result = check(
        make_cylinder(),
        (RestoredMark(MarkKind.SERIAL, "B9999"),),
        Evidence.OUR_RECORDS,
        A_PASS,
        DAY,
    )
    assert "does not rename" in result.refusals[0]


def test_the_maker_has_to_match_too() -> None:
    result = check(
        make_cylinder(),
        (RestoredMark(MarkKind.MANUFACTURER, "PST"),),
        Evidence.OUR_RECORDS,
        A_PASS,
        DAY,
    )
    assert "the maker on the book is NCI" in result.refusals[0]


def test_a_condemned_cylinder_is_not_re_marked() -> None:
    result = check(
        make_cylinder(status=CylinderStatus.CONDEMNED),
        (RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),),
        Evidence.OUR_RECORDS,
        A_PASS,
        DAY,
    )
    assert "is not re-marked" in result.refusals[0]
    with pytest.raises(RuleViolationError, match="is not re-marked"):
        result.require()


def test_the_record_it_rests_on_cannot_be_later(shop_book: object) -> None:
    later = [make_event(performed_on=date(2025, 1, 1))]
    result = check(
        make_cylinder(),
        (RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),),
        Evidence.OUR_RECORDS,
        later,
        DAY,
    )
    assert "dated after the re-marking" in result.refusals[0]


def test_only_standing_passes_support_a_remarking() -> None:
    condemned = make_event(outcome=Outcome.CONDEMN, reasons=("leaked",))
    reversed_pass = make_event().reversed_by("pulled")
    assert supporting_records([condemned, reversed_pass]) == []
    assert len(supporting_records(A_PASS)) == 1
