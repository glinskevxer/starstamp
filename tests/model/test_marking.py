from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.marking import (
    Evidence,
    MarkKind,
    Remarking,
    RestoredMark,
    normalise_mark,
)

DAY = date(2024, 6, 14)


def a_remarking(**changes: object) -> Remarking:
    base: dict[str, object] = {
        "cylinder_key": "NCI/A4471",
        "marked_on": DAY,
        "facility_rin": "A419",
        "technician_badge": "JT7",
        "evidence": Evidence.OUR_RECORDS,
        "marks": (RestoredMark(MarkKind.SPECIFICATION, "DOT-3AA2015"),),
    }
    base.update(changes)
    return Remarking(**base)  # type: ignore[arg-type]


def test_marks_are_normalised() -> None:
    assert normalise_mark("  dot-3aa2015 ") == "DOT-3AA2015"
    assert normalise_mark("06  98") == "06 98"


@pytest.mark.parametrize("text", ["", "!!", "x" * 40])
def test_a_mark_that_is_not_stamped_on_anything(text: str) -> None:
    with pytest.raises(ValidationError, match="not something stamped"):
        normalise_mark(text)


def test_which_marks_say_which_cylinder_it_is() -> None:
    assert MarkKind.SERIAL.is_identity
    assert MarkKind.MANUFACTURER.is_identity
    assert not MarkKind.TARE_WEIGHT.is_identity
    assert MarkKind.MANUFACTURE_DATE.label == "manufacture date"


def test_a_remarking_that_restored_nothing() -> None:
    with pytest.raises(ValidationError, match="restored nothing"):
        a_remarking(marks=())


def test_the_same_mark_twice() -> None:
    with pytest.raises(ValidationError, match="restored twice"):
        a_remarking(
            marks=(
                RestoredMark(MarkKind.SERIAL, "A4471"),
                RestoredMark(MarkKind.SERIAL, "A4472"),
            )
        )


def test_finding_one_mark() -> None:
    remarking = a_remarking(
        marks=(
            RestoredMark(MarkKind.SERIAL, "A4471"),
            RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),
        )
    )
    assert remarking.restored_identity
    found = remarking.of_kind(MarkKind.TARE_WEIGHT)
    assert found is not None
    assert found.reads == "TW 117.5"
    assert remarking.of_kind(MarkKind.SPECIFICATION) is None


def test_evidence_labels() -> None:
    assert Evidence.OUR_RECORDS.is_ours
    assert not Evidence.OWNER_DECLARATION.is_ours
    assert Evidence.MANUFACTURER_LETTER.label == "manufacturer letter"


def test_summaries() -> None:
    line = a_remarking(note="shoulder was polished").summary()
    assert "re-marked under A419" in line
    assert "from our records" in line
    assert "specification DOT-3AA2015" in line
    assert "(shoulder was polished)" in line
