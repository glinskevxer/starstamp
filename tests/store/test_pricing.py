from datetime import date

import pytest

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.money import Money
from starstamp.model.pricing import PriceItem
from starstamp.store.db import Book
from starstamp.store.pricing import PriceRepository


@pytest.fixture
def prices(book: Book) -> PriceRepository:
    repository = PriceRepository(book.connection)
    repository.add(
        PriceItem(
            code="REQUAL_WJ",
            description="water jacket requalification",
            amount=Money.parse("14.50"),
            effective_from=date(2023, 1, 1),
        )
    )
    return repository


def test_the_book_reads_back(prices: PriceRepository) -> None:
    book = prices.book()
    assert book.amount("REQUAL_WJ", date(2023, 6, 1)) == Money.parse("14.50")


def test_two_prices_from_the_same_day(prices: PriceRepository) -> None:
    with pytest.raises(ConflictError, match="already has a price starting"):
        prices.add(
            PriceItem(
                code="REQUAL_WJ",
                description="again",
                amount=Money.parse("16.00"),
                effective_from=date(2023, 1, 1),
            )
        )


def test_raising_a_price_closes_the_old_one(prices: PriceRepository) -> None:
    prices.raise_price(
        "requal-wj", Money.parse("16.00"), date(2024, 1, 1), "water jacket requalification"
    )
    history = prices.for_code("REQUAL_WJ")
    assert len(history) == 2
    assert history[0].effective_until == date(2023, 12, 31)
    book = prices.book()
    assert book.amount("REQUAL_WJ", date(2023, 12, 31)) == Money.parse("14.50")
    assert book.amount("REQUAL_WJ", date(2024, 1, 1)) == Money.parse("16.00")


def test_an_old_invoice_still_finds_its_price(prices: PriceRepository) -> None:
    prices.raise_price("REQUAL_WJ", Money.parse("16.00"), date(2024, 1, 1), "wj")
    prices.raise_price("REQUAL_WJ", Money.parse("17.25"), date(2025, 1, 1), "wj")
    book = prices.book()
    assert book.amount("REQUAL_WJ", date(2023, 5, 5)) == Money.parse("14.50")
    assert book.amount("REQUAL_WJ", date(2024, 5, 5)) == Money.parse("16.00")
    assert book.amount("REQUAL_WJ", date(2025, 5, 5)) == Money.parse("17.25")


def test_a_price_that_does_not_exist_yet(prices: PriceRepository) -> None:
    with pytest.raises(NotFoundError, match="no price for REQUAL_WJ on 2022"):
        prices.book().amount("REQUAL_WJ", date(2022, 1, 1))


def test_current_prices(prices: PriceRepository) -> None:
    prices.raise_price("VALVE", Money.parse("8.00"), date(2024, 1, 1), "valve change")
    assert len(prices.current(date(2024, 6, 1))) == 2
    assert len(prices.current(date(2023, 6, 1))) == 1


def test_the_history_for_a_code_that_has_none(prices: PriceRepository) -> None:
    assert prices.for_code("PAINT") == []
