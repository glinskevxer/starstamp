from datetime import date

import pytest

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.cylinder import CylinderKey
from starstamp.service.imports import ImportService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book

DAY = date(2024, 6, 3)

GOOD = """cylinder,specification,manufactured,service,ree,wall
PST/B12,DOT-3AA2015,06-98,N2,31.2,0.220
PST/B13,DOT-3AL3000,04-12,AR,,
PST/B14,DOT-4BA240,09-05,LPG,,0.087
"""


def test_a_clean_list_goes_in(shop_book: Book) -> None:
    service = ImportService(shop_book)
    result = service.read(GOOD, "WELD1", DAY, write=True)
    assert len(result.accepted) == 3
    assert result.is_clean
    assert result.written
    assert CylinderRepository(shop_book.connection).exists(CylinderKey("PST", "B13"))
    assert "took in 3 cylinders for WELD1" in result.describe()


def test_a_dry_run_writes_nothing(shop_book: Book) -> None:
    service = ImportService(shop_book)
    result = service.read(GOOD, "WELD1", DAY, write=False)
    assert len(result.accepted) == 3
    assert not result.written
    assert not CylinderRepository(shop_book.connection).exists(CylinderKey("PST", "B13"))
    assert "would take in 3" in result.describe()


def test_every_bad_row_is_reported(shop_book: Book) -> None:
    text = (
        "cylinder,specification,manufactured,service\n"
        "PST/B12,DOT-3AA2015,06-98,N2\n"
        "B13,DOT-3AA2015,06-98,N2\n"
        "PST/B14,DOT-9ZZ,06-98,N2\n"
        "PST/B15,DOT-3AA2015,not a month,N2\n"
        "PST/B16,DOT-3AA2015,06-98,krypton\n"
    )
    result = ImportService(shop_book).read(text, "WELD1", DAY, write=False)
    assert len(result.accepted) == 1
    assert len(result.problems) == 4
    details = " ".join(str(problem) for problem in result.problems)
    assert "SYMBOL/SERIAL" in details
    assert "unknown specification family" in details
    assert "stamped month" in details
    assert "unknown gas service" in details


def test_a_row_that_is_already_on_the_books(shop_book: Book) -> None:
    text = "cylinder,specification,manufactured,service\nNCI/A4471,DOT-3AA2015,06-98,N2\n"
    result = ImportService(shop_book).read(text, "WELD1", DAY, write=False)
    assert "already on the books" in str(result.problems[0])


def test_a_duplicate_inside_the_list(shop_book: Book) -> None:
    text = (
        "cylinder,specification,manufactured,service\n"
        "PST/B12,DOT-3AA2015,06-98,N2\n"
        "PST/B12,DOT-3AA2015,06-98,N2\n"
    )
    result = ImportService(shop_book).read(text, "WELD1", DAY, write=False)
    assert len(result.accepted) == 1
    assert "twice in this list" in str(result.problems[0])


def test_a_list_missing_a_column(shop_book: Book) -> None:
    with pytest.raises(ConflictError, match="missing columns: service"):
        ImportService(shop_book).read(
            "cylinder,specification,manufactured\nPST/B12,DOT-3AA2015,06-98\n",
            "WELD1",
            DAY,
            write=False,
        )


def test_an_account_that_is_not_open(shop_book: Book) -> None:
    with pytest.raises(NotFoundError):
        ImportService(shop_book).read(GOOD, "FIRE7", DAY, write=False)


def test_the_wall_is_marked_as_coming_from_the_customer(shop_book: Book) -> None:
    ImportService(shop_book).read(GOOD, "WELD1", DAY, write=True)
    cylinder = CylinderRepository(shop_book.connection).by_key(CylinderKey("PST", "B12"))
    assert cylinder.wall_source == "customer list"
    assert cylinder.require_wall() == 220


def test_an_empty_list(shop_book: Book) -> None:
    result = ImportService(shop_book).read(
        "cylinder,specification,manufactured,service\n", "WELD1", DAY, write=True
    )
    assert result.accepted == ()
    assert result.describe() == "took in 0 cylinders for WELD1"
