from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind
from starstamp.model.service import ARGON, NITROGEN
from starstamp.model.units import Pressure
from starstamp.reporting import gases
from starstamp.service.filling import FillingService
from starstamp.store.db import Book

from ..support.factories import make_cylinder, make_observation
from ..support.requests import requalify
from ..support.shop import stock

FIRST = date(2024, 6, 1)
LAST = date(2024, 6, 30)
KEY = CylinderKey("NCI", "A4471")


def test_an_empty_shop(shop_book: Book) -> None:
    shop_book.connection.execute("DELETE FROM cylinder")
    report = gases.build(shop_book, FIRST, LAST)
    assert report.busy == ()
    assert "holds nothing" in report.describe()
    assert gases.render(report) == report.describe()


def test_the_fleet_is_counted_by_gas(shop_book: Book) -> None:
    stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12"), service=ARGON))
    report = gases.build(shop_book, FIRST, LAST)
    held = {row.service.code: row.on_the_books for row in report.busy}
    assert held == {"AR": 1, "N2": 1}


def test_work_and_condemnations_are_counted(shop_book: Book) -> None:
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    requalify(shop_book)
    requalify(shop_book, key=other, observations=(make_observation(DefectKind.BULGE),))
    report = gases.build(shop_book, FIRST, LAST)
    nitrogen = next(row for row in report.rows if row.service.code == "N2")
    assert nitrogen.tested == 2
    assert nitrogen.condemned == 1
    assert float(nitrogen.condemn_rate) == 50.0


def test_fills_are_counted(shop_book: Book) -> None:
    requalify(shop_book)
    FillingService(shop_book).record(
        KEY, NITROGEN, date(2024, 6, 25), "JT7", pressure=Pressure(2015)
    )
    report = gases.build(shop_book, FIRST, LAST)
    nitrogen = next(row for row in report.rows if row.service.code == "N2")
    assert nitrogen.filled == 1


def test_the_worst_gas_needs_enough_work_behind_it(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    report = gases.build(shop_book, FIRST, LAST)
    assert report.worst() is None


def test_a_gas_nobody_touched_is_idle(shop_book: Book) -> None:
    report = gases.build(shop_book, FIRST, LAST)
    codes = {row.service.code for row in report.busy}
    assert "CL2" not in codes
    assert "N2" in codes


def test_rendering(shop_book: Book) -> None:
    requalify(shop_book)
    text = gases.render(gases.build(shop_book, FIRST, LAST))
    assert "nitrogen" in text
    assert "1 cylinders across 1 gases" in text
