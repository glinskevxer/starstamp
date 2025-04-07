from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.model.defect import DefectKind
from starstamp.model.disposal import DisposalMethod
from starstamp.service.disposal import DisposalService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book

from ..support.factories import make_observation
from ..support.requests import requalify
from ..support.shop import DAY

KEY = CylinderKey("NCI", "A4471")


def test_a_condemned_cylinder_is_drilled_and_scrapped(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    disposal = DisposalService(shop_book).dispose(
        KEY, DisposalMethod.DRILLED, date(2024, 6, 20), "JT7", scrap_ticket="SC-4411"
    )
    assert disposal.scrap_ticket == "SC-4411"
    assert CylinderRepository(shop_book.connection).by_key(KEY).status is CylinderStatus.SCRAPPED


def test_holding_one_for_its_owner_leaves_it_condemned(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    DisposalService(shop_book).dispose(KEY, DisposalMethod.HELD_FOR_OWNER, date(2024, 6, 20), "JT7")
    assert CylinderRepository(shop_book.connection).by_key(KEY).status is CylinderStatus.CONDEMNED


def test_a_cylinder_that_was_never_condemned(shop_book: Book) -> None:
    with pytest.raises(RuleViolationError, match="only a condemned cylinder"):
        DisposalService(shop_book).dispose(KEY, DisposalMethod.DRILLED, date(2024, 6, 20), "JT7")


def test_a_cylinder_condemned_by_hand_with_no_record(shop_book: Book) -> None:
    CylinderRepository(shop_book.connection).set_status(KEY, CylinderStatus.CONDEMNED)
    with pytest.raises(RuleViolationError, match="no standing condemnation"):
        DisposalService(shop_book).dispose(KEY, DisposalMethod.DRILLED, date(2024, 6, 20), "JT7")


def test_the_clock_runs_from_the_record_of_test(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    disposal = DisposalService(shop_book).dispose(
        KEY, DisposalMethod.CRUSHED, date(2024, 7, 20), "JT7"
    )
    assert disposal.condemned_on == DAY
    assert disposal.is_late
    assert disposal.days_taken == 38


def test_what_is_still_outstanding(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    service = DisposalService(shop_book)
    waiting = service.outstanding(date(2024, 6, 20))
    assert len(waiting) == 1
    assert waiting[0].days_waiting == 8
    assert waiting[0].due_by == date(2024, 7, 12)
    assert not waiting[0].is_late
    assert "due by 2024-07-12" in waiting[0].describe()


def test_late_ones_are_flagged(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    service = DisposalService(shop_book)
    assert service.late(date(2024, 7, 12)) == []
    late = service.late(date(2024, 7, 13))
    assert len(late) == 1
    assert "LATE" in late[0].describe()


def test_a_dealt_with_cylinder_drops_off_the_list(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    service = DisposalService(shop_book)
    service.dispose(KEY, DisposalMethod.HELD_FOR_OWNER, date(2024, 6, 20), "JT7")
    assert service.outstanding(date(2024, 6, 21)) == []


def test_a_cylinder_going_home_is_rendered_first(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    disposal = DisposalService(shop_book).dispose(
        KEY,
        DisposalMethod.NECK_CUT,
        date(2024, 6, 20),
        "JT7",
        witness_badge="MR2",
        returned_to_owner=True,
    )
    assert disposal.returned_to_owner
    assert "returned to the owner" in disposal.summary()


def test_the_badges_are_normalised_and_checked(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    disposal = DisposalService(shop_book).dispose(
        KEY, DisposalMethod.DRILLED, date(2024, 6, 20), "jt7", witness_badge="mr2"
    )
    assert disposal.technician_badge == "JT7"
    assert disposal.witness_badge == "MR2"


def test_a_technician_who_is_not_on_the_bench(shop_book: Book) -> None:
    from starstamp.errors import NotFoundError

    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    with pytest.raises(NotFoundError, match="no technician ZZ9"):
        DisposalService(shop_book).dispose(KEY, DisposalMethod.DRILLED, date(2024, 6, 20), "zz9")
