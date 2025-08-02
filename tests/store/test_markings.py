from datetime import date

import pytest

from starstamp.errors import NotFoundError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.marking import Evidence, MarkKind, Remarking, RestoredMark
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.markings import RemarkingRepository
from starstamp.store.owners import OwnerRepository

from ..support.factories import make_cylinder

KEY = CylinderKey("NCI", "A4471")
DAY = date(2024, 6, 14)


@pytest.fixture
def markings(
    book: Book, owners: OwnerRepository, cylinders: CylinderRepository
) -> RemarkingRepository:
    cylinders.add(make_cylinder(key=KEY), owners.id_of("WELD1"), date(2024, 1, 2))
    return RemarkingRepository(book.connection)


def a_remarking(**changes: object) -> Remarking:
    base: dict[str, object] = {
        "cylinder_key": str(KEY),
        "marked_on": DAY,
        "facility_rin": "A419",
        "technician_badge": "JT7",
        "evidence": Evidence.OUR_RECORDS,
        "marks": (RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),),
    }
    base.update(changes)
    return Remarking(**base)  # type: ignore[arg-type]


def test_a_remarking_round_trips(
    markings: RemarkingRepository, cylinders: CylinderRepository
) -> None:
    written = markings.add(a_remarking(note="polished"), cylinders.id_of(KEY))
    assert written.remarking_id is not None
    read_back = markings.by_id(written.remarking_id)
    assert read_back.note == "polished"
    assert read_back.marks[0].reads == "TW 117.5"
    assert read_back.cylinder_key == "NCI/A4471"


def test_several_marks_in_one_go(
    markings: RemarkingRepository, cylinders: CylinderRepository
) -> None:
    written = markings.add(
        a_remarking(
            marks=(
                RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),
                RestoredMark(MarkKind.SERVICE_PRESSURE, "2015"),
            )
        ),
        cylinders.id_of(KEY),
    )
    assert written.remarking_id is not None
    assert len(markings.marks_for(written.remarking_id)) == 2


def test_history_and_windows(markings: RemarkingRepository, cylinders: CylinderRepository) -> None:
    markings.add(a_remarking(), cylinders.id_of(KEY))
    markings.add(a_remarking(marked_on=date(2024, 7, 4)), cylinders.id_of(KEY))
    assert len(markings.for_cylinder(KEY)) == 2
    assert len(markings.between(date(2024, 6, 1), date(2024, 6, 30))) == 1
    assert markings.count() == 2


def test_a_missing_remarking(markings: RemarkingRepository) -> None:
    with pytest.raises(NotFoundError, match="no re-marking 99"):
        markings.by_id(99)


def test_a_cylinder_that_was_never_re_marked(markings: RemarkingRepository) -> None:
    assert markings.for_cylinder(KEY) == []
