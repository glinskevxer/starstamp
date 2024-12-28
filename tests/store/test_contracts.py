from datetime import date
from fractions import Fraction

import pytest

from starstamp.errors import ConflictError
from starstamp.model.contract import ContractTerm
from starstamp.model.money import Money
from starstamp.store.contracts import ContractRepository
from starstamp.store.db import Book
from starstamp.store.owners import OwnerRepository

FROM = date(2024, 1, 1)


@pytest.fixture
def contracts(book: Book, owners: OwnerRepository) -> ContractRepository:
    return ContractRepository(book.connection)


def a_term(**changes: object) -> ContractTerm:
    base: dict[str, object] = {
        "owner_code": "WELD1",
        "code": "REQUAL_WJ",
        "effective_from": FROM,
        "amount": Money.parse("12.00"),
    }
    base.update(changes)
    return ContractTerm(**base)  # type: ignore[arg-type]


def test_a_flat_term_round_trips(contracts: ContractRepository, owners: OwnerRepository) -> None:
    contracts.add(a_term(), owners.id_of("WELD1"))
    contract = contracts.contract("weld1")
    assert contract.price("REQUAL_WJ", FROM, Money.parse("14.50")) == Money.parse("12.00")


def test_a_discount_term_round_trips(
    contracts: ContractRepository, owners: OwnerRepository
) -> None:
    contracts.add(a_term(amount=None, discount_percent=Fraction(15, 2)), owners.id_of("WELD1"))
    term = contracts.contract("WELD1").terms[0]
    assert term.discount_percent == Fraction(15, 2)
    assert term.price_from(Money.parse("20.00")) == Money.parse("18.50")


def test_two_terms_from_the_same_day(
    contracts: ContractRepository, owners: OwnerRepository
) -> None:
    contracts.add(a_term(), owners.id_of("WELD1"))
    with pytest.raises(ConflictError, match="already has a REQUAL_WJ term"):
        contracts.add(a_term(), owners.id_of("WELD1"))


def test_agreeing_a_new_term_closes_the_old_one(
    contracts: ContractRepository, owners: OwnerRepository
) -> None:
    contracts.add(a_term(), owners.id_of("WELD1"))
    contracts.agree(
        a_term(amount=Money.parse("13.00"), effective_from=date(2025, 1, 1)),
        owners.id_of("WELD1"),
    )
    history = contracts.for_code("WELD1", "requal-wj")
    assert len(history) == 2
    assert history[0].effective_until == date(2024, 12, 31)
    contract = contracts.contract("WELD1")
    assert contract.price("REQUAL_WJ", date(2024, 6, 1), Money.parse("14.50")).cents == 1200
    assert contract.price("REQUAL_WJ", date(2025, 6, 1), Money.parse("14.50")).cents == 1300


def test_current_terms_and_accounts(contracts: ContractRepository, owners: OwnerRepository) -> None:
    contracts.add(a_term(), owners.id_of("WELD1"))
    contracts.add(a_term(code="HANDLING", amount=Money.parse("4.00")), owners.id_of("WELD1"))
    assert len(contracts.current("WELD1", date(2024, 6, 1))) == 2
    assert contracts.current("WELD1", date(2023, 6, 1)) == []
    assert contracts.accounts_with_terms() == ["WELD1"]


def test_an_account_with_nothing_agreed(contracts: ContractRepository) -> None:
    assert contracts.contract("WELD1").terms == ()
    assert contracts.accounts_with_terms() == []
