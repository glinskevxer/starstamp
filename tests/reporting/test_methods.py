from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind
from starstamp.model.method import Method
from starstamp.reporting import methods
from starstamp.store.db import Book

from ..support.factories import make_cylinder, make_observation
from ..support.requests import requalify
from ..support.shop import stock

FIRST = date(2024, 6, 1)
LAST = date(2024, 6, 30)


def test_a_quiet_window(shop_book: Book) -> None:
    mix = methods.build(shop_book, FIRST, LAST)
    assert mix.used == ()
    assert mix.busiest() is None
    assert "nothing was requalified" in mix.describe()
    assert methods.render(mix) == mix.describe()


def test_one_method_used(shop_book: Book) -> None:
    requalify(shop_book)
    mix = methods.build(shop_book, FIRST, LAST)
    assert len(mix.used) == 1
    row = mix.used[0]
    assert row.method is Method.VOLUMETRIC
    assert row.performed == 1
    assert row.starred == 1
    assert row.people == frozenset({"JT7"})


def test_the_rates(shop_book: Book) -> None:
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    requalify(shop_book)
    requalify(shop_book, key=other, observations=(make_observation(DefectKind.BULGE),))
    row = methods.build(shop_book, FIRST, LAST).used[0]
    assert float(row.condemn_rate) == 50.0
    assert float(row.star_rate) == 50.0


def test_the_methods_nobody_used_are_named(shop_book: Book) -> None:
    requalify(shop_book)
    mix = methods.build(shop_book, FIRST, LAST)
    assert Method.PROOF_PRESSURE in mix.unused
    assert Method.VOLUMETRIC not in mix.unused
    assert "not used:" in methods.render(mix)


def test_the_busiest_method_and_its_share(shop_book: Book) -> None:
    requalify(shop_book)
    mix = methods.build(shop_book, FIRST, LAST)
    busiest = mix.busiest()
    assert busiest is not None
    assert busiest.method is Method.VOLUMETRIC
    assert "volumetric is 100% of it" in mix.describe()


def test_rendering(shop_book: Book) -> None:
    requalify(shop_book)
    text = methods.render(methods.build(shop_book, FIRST, LAST))
    assert "volumetric" in text
    assert "1 cylinders across 1 methods" in text
