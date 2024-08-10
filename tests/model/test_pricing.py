from datetime import date

import pytest

from starstamp.errors import NotFoundError, ValidationError
from starstamp.model.method import Method
from starstamp.model.money import Money
from starstamp.model.pricing import (
    PriceBook,
    PriceItem,
    code_for,
    normalise_charge_code,
)


def an_item(**changes: object) -> PriceItem:
    base: dict[str, object] = {
        "code": "REQUAL_WJ",
        "description": "water jacket requalification",
        "amount": Money.parse("14.50"),
        "effective_from": date(2023, 1, 1),
    }
    base.update(changes)
    return PriceItem(**base)  # type: ignore[arg-type]


def test_codes_normalise() -> None:
    assert normalise_charge_code(" requal-wj ") == "REQUAL_WJ"
    with pytest.raises(ValidationError, match="2 to 16"):
        normalise_charge_code("R")


def test_every_method_has_a_charge_code() -> None:
    for method in Method:
        assert code_for(method).startswith("REQUAL_")


def test_an_item_that_ends_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="end before it started"):
        an_item(effective_until=date(2022, 1, 1))


def test_the_window() -> None:
    item = an_item(effective_until=date(2024, 12, 31))
    assert not item.applies_on(date(2022, 12, 31))
    assert item.applies_on(date(2023, 1, 1))
    assert item.applies_on(date(2024, 12, 31))
    assert not item.applies_on(date(2025, 1, 1))


def test_an_open_ended_item_runs_on() -> None:
    assert an_item().applies_on(date(2099, 1, 1))


def test_the_book_reads_the_price_for_the_day() -> None:
    book = PriceBook(
        (
            an_item(amount=Money.parse("14.50"), effective_until=date(2023, 12, 31)),
            an_item(amount=Money.parse("16.00"), effective_from=date(2024, 1, 1)),
        )
    )
    assert book.amount("REQUAL_WJ", date(2023, 6, 1)) == Money.parse("14.50")
    assert book.amount("REQUAL_WJ", date(2024, 6, 1)) == Money.parse("16.00")


def test_the_latest_effective_price_wins_when_two_overlap() -> None:
    book = PriceBook(
        (
            an_item(amount=Money.parse("14.50")),
            an_item(amount=Money.parse("16.00"), effective_from=date(2024, 1, 1)),
        )
    )
    assert book.amount("requal-wj", date(2024, 6, 1)) == Money.parse("16.00")


def test_a_day_before_any_price() -> None:
    book = PriceBook((an_item(),))
    with pytest.raises(NotFoundError, match="no price for REQUAL_WJ on 2022-06-01"):
        book.amount("REQUAL_WJ", date(2022, 6, 1))


def test_a_code_the_book_does_not_carry() -> None:
    with pytest.raises(NotFoundError, match="no price for VALVE"):
        PriceBook((an_item(),)).amount("VALVE", date(2024, 1, 1))


def test_codes_and_growth() -> None:
    book = PriceBook((an_item(),)).with_item(an_item(code="VALVE"))
    assert book.codes() == ["REQUAL_WJ", "VALVE"]
    assert len(book.items) == 2


def test_item_text() -> None:
    assert str(an_item()) == "REQUAL_WJ $14.50 from 2023-01-01"
