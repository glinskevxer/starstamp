from datetime import date
from fractions import Fraction

import pytest

from starstamp.errors import NotFoundError, ValidationError
from starstamp.model.contract import Contract, ContractTerm
from starstamp.model.money import Money

FROM = date(2024, 1, 1)
BOOK = Money.parse("14.50")


def a_term(**changes: object) -> ContractTerm:
    base: dict[str, object] = {
        "owner_code": "WELD1",
        "code": "REQUAL_WJ",
        "effective_from": FROM,
        "amount": Money.parse("12.00"),
    }
    base.update(changes)
    return ContractTerm(**base)  # type: ignore[arg-type]


def test_a_term_is_a_price_or_a_discount_but_not_both() -> None:
    with pytest.raises(ValidationError, match="one of them"):
        a_term(discount_percent=Fraction(10))
    with pytest.raises(ValidationError, match="one of them"):
        a_term(amount=None)


def test_a_discount_has_to_be_a_discount() -> None:
    with pytest.raises(ValidationError, match="between 0 and 100"):
        a_term(amount=None, discount_percent=Fraction(0))
    with pytest.raises(ValidationError, match="between 0 and 100"):
        a_term(amount=None, discount_percent=Fraction(100))


def test_a_term_that_ends_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="ends before it starts"):
        a_term(effective_until=date(2023, 1, 1))


def test_a_flat_price_ignores_the_book() -> None:
    assert a_term().price_from(BOOK) == Money.parse("12.00")
    assert a_term().is_flat


def test_a_discount_comes_off_the_book() -> None:
    term = a_term(amount=None, discount_percent=Fraction(10))
    assert term.price_from(BOOK) == Money.parse("13.05")
    assert not term.is_flat


def test_a_discount_rounds_half_up() -> None:
    term = a_term(amount=None, discount_percent=Fraction(15))
    assert term.price_from(Money.parse("14.55")).cents == 1237


def test_the_window() -> None:
    term = a_term(effective_until=date(2024, 12, 31))
    assert not term.applies_on(date(2023, 12, 31))
    assert term.applies_on(FROM)
    assert term.applies_on(date(2024, 12, 31))
    assert not term.applies_on(date(2025, 1, 1))


def test_a_contract_reads_the_term_in_force() -> None:
    contract = Contract(
        "WELD1",
        (
            a_term(effective_until=date(2024, 6, 30)),
            a_term(amount=Money.parse("13.00"), effective_from=date(2024, 7, 1)),
        ),
    )
    assert contract.price("REQUAL_WJ", date(2024, 3, 1), BOOK) == Money.parse("12.00")
    assert contract.price("REQUAL_WJ", date(2024, 8, 1), BOOK) == Money.parse("13.00")


def test_a_code_with_no_term_falls_back_to_the_book() -> None:
    contract = Contract("WELD1", (a_term(),))
    assert contract.price("HANDLING", date(2024, 3, 1), BOOK) == BOOK
    assert contract.term_on("HANDLING", date(2024, 3, 1)) is None


def test_requiring_a_term_that_is_not_there() -> None:
    with pytest.raises(NotFoundError, match="no agreed price for HANDLING"):
        Contract("WELD1", ()).require_term("HANDLING", date(2024, 3, 1))


def test_the_codes_an_account_has_agreed() -> None:
    contract = Contract("WELD1", (a_term(), a_term(code="HANDLING")))
    assert contract.codes() == ["HANDLING", "REQUAL_WJ"]


def test_term_text() -> None:
    assert str(a_term()) == "WELD1 REQUAL_WJ at $12.00"
    assert str(a_term(amount=None, discount_percent=Fraction(10))) == "WELD1 REQUAL_WJ less 10.0%"
