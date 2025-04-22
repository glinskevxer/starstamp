from datetime import date

import pytest

from starstamp.errors import StarstampError
from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.service.batch import BatchService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book

from ..support.factories import make_cylinder
from ..support.shop import DAY, SYSTEM, stock

SHEET = """cylinder,applied,total,permanent,hold,defects
NCI/A4471,3358,110.0,2.0,30,
PST/B12,3358,110.0,2.0,30,
"""


@pytest.fixture
def two_cylinders(shop_book: Book) -> Book:
    stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    return shop_book


def test_a_clean_sheet_goes_through(two_cylinders: Book) -> None:
    result = BatchService(two_cylinders).run(SHEET, DAY, "JT7", SYSTEM)
    assert result.recorded == 2
    assert result.passed == 2
    assert result.is_clean
    assert "2 recorded, 2 passed, 0 rows left out" in result.describe()


def test_a_bad_row_is_reported_and_the_rest_go_through(two_cylinders: Book) -> None:
    sheet = SHEET + "NOPE/X1,3358,110.0,2.0,30,\n"
    result = BatchService(two_cylinders).run(sheet, DAY, "JT7", SYSTEM)
    assert result.recorded == 2
    assert len(result.faults) == 1
    assert "no cylinder NOPE/X1" in str(result.faults[0])
    assert "1 rows left out" in result.describe()


def test_a_row_the_rules_refuse(two_cylinders: Book) -> None:
    sheet = "cylinder,applied,total,permanent\nNCI/A4471,3000,110.0,2.0\n"
    result = BatchService(two_cylinders).run(sheet, DAY, "JT7", SYSTEM)
    assert result.recorded == 0
    assert "short of the required" in str(result.faults[0])


def test_a_condemning_row_is_still_recorded(two_cylinders: Book) -> None:
    sheet = "cylinder,applied,total,permanent\nNCI/A4471,3358,100.0,12.0\n"
    result = BatchService(two_cylinders).run(sheet, DAY, "JT7", SYSTEM)
    assert result.recorded == 1
    assert result.passed == 0
    status = CylinderRepository(two_cylinders.connection).by_key(CylinderKey("NCI", "A4471")).status
    assert status is CylinderStatus.CONDEMNED


def test_defects_come_off_the_sheet(two_cylinders: Book) -> None:
    sheet = "cylinder,applied,total,permanent,defects\nNCI/A4471,3358,110.0,2.0,pitting:0.050\n"
    result = BatchService(two_cylinders).run(sheet, DAY, "JT7", SYSTEM)
    assert result.recorded == 1
    assert result.passed == 0
    assert "isolated pitting" in result.results[0].event.reasons[0]


def test_an_unreadable_number(two_cylinders: Book) -> None:
    sheet = "cylinder,applied,total,permanent\nNCI/A4471,lots,110.0,2.0\n"
    result = BatchService(two_cylinders).run(sheet, DAY, "JT7", SYSTEM)
    assert "pressure must be whole psi" in str(result.faults[0])


def test_a_sheet_with_the_wrong_columns(two_cylinders: Book) -> None:
    with pytest.raises(StarstampError, match="missing columns: total, permanent"):
        BatchService(two_cylinders).run("cylinder,applied\nNCI/A4471,3358\n", DAY, "JT7", SYSTEM)


def test_an_empty_sheet(two_cylinders: Book) -> None:
    result = BatchService(two_cylinders).run(
        "cylinder,applied,total,permanent\n", DAY, "JT7", SYSTEM
    )
    assert result.recorded == 0
    assert result.is_clean


def test_the_hold_time_can_come_off_the_sheet(two_cylinders: Book) -> None:
    sheet = "cylinder,applied,total,permanent,hold\nNCI/A4471,3358,110.0,2.0,25\n"
    result = BatchService(two_cylinders).run(sheet, DAY, "JT7", SYSTEM)
    assert "short of the 30s" in str(result.faults[0])


def test_the_day_is_the_one_the_sheet_was_run_for(two_cylinders: Book) -> None:
    result = BatchService(two_cylinders).run(SHEET, DAY, "JT7", SYSTEM)
    assert result.day == DAY
    assert all(item.event.performed_on == date(2024, 6, 12) for item in result.results)
