from datetime import date
from fractions import Fraction

from starstamp.model.cylinder import CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import DefectKind
from starstamp.reporting import condemnation
from starstamp.store.db import Book
from starstamp.store.events import EventRepository

from ..support.factories import make_cylinder, make_observation
from ..support.requests import requalify
from ..support.shop import stock

KEY = CylinderKey("NCI", "A4471")
FIRST = date(2024, 1, 1)
LAST = date(2024, 12, 31)


def test_a_quiet_window(shop_book: Book) -> None:
    analysis = condemnation.build(shop_book, FIRST, LAST)
    assert analysis.count == 0
    assert analysis.average_age() == 0
    assert analysis.oldest() is None
    assert "nothing condemned" in condemnation.render(analysis)


def test_one_condemnation(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    analysis = condemnation.build(shop_book, FIRST, LAST)
    assert analysis.count == 1
    item = analysis.condemnations[0]
    assert item.age_years == 26
    assert item.cause == "bulge"


def test_grouping(shop_book: Book) -> None:
    other = stock(
        shop_book,
        make_cylinder(key=CylinderKey("PST", "B12"), manufactured=StampedMonth(2014, 3)),
    )
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    requalify(shop_book, key=other, observations=(make_observation(DefectKind.CRACK),))
    analysis = condemnation.build(shop_book, FIRST, LAST)
    assert analysis.count == 2
    assert set(analysis.by_cause()) == {"bulge", "crack"}
    assert analysis.by_owner() == {"WELD1": 2}
    assert analysis.by_specification() == {"DOT-3AA2015": 2}
    assert analysis.by_decade() == {"1990s": 1, "2010s": 1}


def test_the_average_age_is_exact(shop_book: Book) -> None:
    other = stock(
        shop_book,
        make_cylinder(key=CylinderKey("PST", "B12"), manufactured=StampedMonth(2014, 3)),
    )
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    requalify(shop_book, key=other, observations=(make_observation(DefectKind.CRACK),))
    analysis = condemnation.build(shop_book, FIRST, LAST)
    assert analysis.average_age() == Fraction(36, 2)


def test_the_oldest_one(shop_book: Book) -> None:
    other = stock(
        shop_book,
        make_cylinder(key=CylinderKey("PST", "B12"), manufactured=StampedMonth(2014, 3)),
    )
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    requalify(shop_book, key=other, observations=(make_observation(DefectKind.CRACK),))
    oldest = condemnation.build(shop_book, FIRST, LAST).oldest()
    assert oldest is not None
    assert oldest.cylinder.key == KEY


def test_a_reversed_condemnation_does_not_count(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    EventRepository(shop_book.connection).reverse(1, "wrong cylinder")
    assert condemnation.build(shop_book, FIRST, LAST).count == 0


def test_rendering(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    text = condemnation.render(condemnation.build(shop_book, FIRST, LAST))
    assert "1 condemned between" in text
    assert "NCI/A4471" in text
    assert "1990s" in text
    assert "specification" in text
