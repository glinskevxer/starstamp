from starstamp.model.cylinder import CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.model.method import Method
from starstamp.model.specification import parse_specification
from starstamp.reporting import specifications
from starstamp.store.db import Book

from ..support.factories import make_cylinder
from ..support.shop import DAY, stock


def test_an_empty_book(shop_book: Book) -> None:
    shop_book.connection.execute("DELETE FROM cylinder")
    report = specifications.build(shop_book, DAY)
    assert report.rows == ()
    assert "nothing on the books" in report.describe()
    assert specifications.render(report) == report.describe()


def test_the_fleet_is_grouped_by_marking(shop_book: Book) -> None:
    stock(
        shop_book,
        make_cylinder(
            key=CylinderKey("LUX", "AL9"),
            specification=parse_specification("DOT-3AL3000"),
        ),
    )
    report = specifications.build(shop_book, DAY)
    assert [row.marking for row in report.rows] == ["DOT-3AA2015", "DOT-3AL3000"]
    assert all(row.cylinders == 1 for row in report.rows)


def test_the_oldest_year_is_reported(shop_book: Book) -> None:
    stock(
        shop_book,
        make_cylinder(key=CylinderKey("PST", "B12"), manufactured=StampedMonth(1979, 4)),
    )
    report = specifications.build(shop_book, DAY)
    assert report.rows[0].oldest_year == 1979


def test_what_the_shop_can_do_comes_off_its_approval(shop_book: Book) -> None:
    report = specifications.build(shop_book, DAY)
    row = report.rows[0]
    assert Method.VOLUMETRIC in row.covered
    assert not row.missing


def test_a_specification_nothing_covers(shop_book: Book) -> None:
    shop_book.connection.execute("UPDATE facility SET methods = 'acetylene_visual'")
    report = specifications.build(shop_book, DAY)
    assert report.uncovered
    assert "nothing the shop holds covers DOT-3AA2015" in report.describe()


def test_a_book_with_no_shop_still_lists_the_fleet(shop_book: Book) -> None:
    shop_book.connection.execute("DELETE FROM facility")
    report = specifications.build(shop_book, DAY)
    assert report.rows
    assert not report.rows[0].is_covered


def test_rendering(shop_book: Book) -> None:
    text = specifications.render(specifications.build(shop_book, DAY))
    assert "DOT-3AA2015" in text
    assert "1 cylinders across 1 specifications" in text
