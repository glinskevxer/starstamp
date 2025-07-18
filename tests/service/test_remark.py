from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.marking import Evidence, MarkKind, RestoredMark
from starstamp.service.remark import RemarkService
from starstamp.store.db import Book

from ..support.requests import requalify

KEY = CylinderKey("NCI", "A4471")
DAY = date(2024, 6, 14)


def test_restoring_a_mark_from_our_own_record(shop_book: Book) -> None:
    requalify(shop_book)
    outcome = RemarkService(shop_book).restore(
        KEY,
        (RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),),
        Evidence.OUR_RECORDS,
        DAY,
        "JT7",
        note="shoulder polished",
    )
    assert outcome.supporting_records == 1
    assert "on 1 records of ours" in outcome.describe()
    assert outcome.remarking.remarking_id is not None


def test_a_cylinder_with_no_history_here(shop_book: Book) -> None:
    with pytest.raises(RuleViolationError, match="no standing record of test here"):
        RemarkService(shop_book).restore(
            KEY,
            (RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),),
            Evidence.OUR_RECORDS,
            DAY,
            "JT7",
        )


def test_a_serial_cannot_be_restored_on_a_customers_word(shop_book: Book) -> None:
    requalify(shop_book)
    with pytest.raises(RuleViolationError, match="not evidence for the serial"):
        RemarkService(shop_book).restore(
            KEY,
            (RestoredMark(MarkKind.SERIAL, "A4471"),),
            Evidence.OWNER_DECLARATION,
            DAY,
            "JT7",
        )


def test_the_shop_number_has_to_be_in_force(shop_book: Book) -> None:
    requalify(shop_book)
    with pytest.raises(RuleViolationError, match="not in force"):
        RemarkService(shop_book).restore(
            KEY,
            (RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),),
            Evidence.OUR_RECORDS,
            date(2027, 1, 4),
            "JT7",
        )


def test_the_history_reads_back(shop_book: Book) -> None:
    requalify(shop_book)
    service = RemarkService(shop_book)
    service.restore(
        KEY,
        (
            RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),
            RestoredMark(MarkKind.SERVICE_PRESSURE, "2015"),
        ),
        Evidence.OUR_RECORDS,
        DAY,
        "JT7",
    )
    history = service.history(KEY)
    assert len(history) == 1
    assert len(history[0].marks) == 2
    assert history[0].of_kind(MarkKind.SERVICE_PRESSURE) is not None


def test_what_the_book_could_stand_behind(shop_book: Book) -> None:
    found = RemarkService(shop_book).what_we_could_restore(KEY)
    assert found[MarkKind.SERIAL] == "A4471"
    assert found[MarkKind.MANUFACTURER] == "NCI"
    assert found[MarkKind.SPECIFICATION] == "DOT-3AA2015"
    assert found[MarkKind.SERVICE_PRESSURE] == "2015"
    assert found[MarkKind.REJECTION_LIMIT] == "125.0"


def test_a_cylinder_with_nothing_measured(shop_book: Book) -> None:
    from ..support.factories import make_cylinder
    from ..support.shop import stock

    key = stock(
        shop_book,
        make_cylinder(key=CylinderKey("PST", "B12"), rejection_elastic_expansion=None),
    )
    found = RemarkService(shop_book).what_we_could_restore(key)
    assert MarkKind.REJECTION_LIMIT not in found
    assert MarkKind.TARE_WEIGHT not in found


def test_a_technician_who_is_not_on_the_bench(shop_book: Book) -> None:
    from starstamp.errors import NotFoundError

    requalify(shop_book)
    with pytest.raises(NotFoundError, match="no technician ZZ9"):
        RemarkService(shop_book).restore(
            KEY,
            (RestoredMark(MarkKind.TARE_WEIGHT, "TW 117.5"),),
            Evidence.OUR_RECORDS,
            DAY,
            "zz9",
        )
