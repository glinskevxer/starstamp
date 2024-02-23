from datetime import date

import pytest

from starstamp.errors import ConflictError, NotFoundError, ValidationError
from starstamp.model.owner import OwnerAccount, normalise_owner_code
from starstamp.store.owners import OwnerRepository


def test_code_is_normalised() -> None:
    assert normalise_owner_code(" weld-1 ") == "WELD_1"


@pytest.mark.parametrize("text", ["", "A", "_ABC", "A" * 17])
def test_bad_codes_are_refused(text: str) -> None:
    with pytest.raises(ValidationError):
        normalise_owner_code(text)


def test_account_round_trips(owners: OwnerRepository) -> None:
    account = owners.by_code("weld1")
    assert account.name == "Cascade Welding Supply"
    assert account.terms_days == 30
    assert account.is_open


def test_duplicate_codes_are_refused(owners: OwnerRepository) -> None:
    with pytest.raises(ConflictError, match="already on the books"):
        owners.add(OwnerAccount(code="WELD1", name="Someone Else", opened_on=date(2020, 1, 1)))


def test_a_missing_account_is_not_found(owners: OwnerRepository) -> None:
    with pytest.raises(NotFoundError, match="no account NOPE"):
        owners.by_code("nope")


def test_ids_and_codes_map_both_ways(owners: OwnerRepository) -> None:
    owner_id = owners.id_of("WELD1")
    assert owners.code_of(owner_id) == "WELD1"
    with pytest.raises(NotFoundError):
        owners.code_of(9999)


def test_closing_and_reopening(owners: OwnerRepository) -> None:
    closed = owners.close("WELD1", date(2024, 6, 30))
    assert closed.closed_on == date(2024, 6, 30)
    assert not closed.is_open
    with pytest.raises(ConflictError, match="closed on"):
        owners.close("WELD1", date(2024, 7, 1))
    reopened = owners.reopen("WELD1")
    assert reopened.is_open
    with pytest.raises(ConflictError, match="already open"):
        owners.reopen("WELD1")


def test_closing_before_opening_is_refused(owners: OwnerRepository) -> None:
    with pytest.raises(ConflictError, match="opened on"):
        owners.close("WELD1", date(2018, 1, 1))


def test_open_on_a_day(owners: OwnerRepository) -> None:
    owners.add(OwnerAccount(code="FIRE7", name="Sanpete Fire District", opened_on=date(2023, 1, 5)))
    assert len(owners.open_on(date(2023, 1, 4))) == 1
    assert len(owners.open_on(date(2023, 1, 5))) == 2
    assert [account.code for account in owners.all()] == ["FIRE7", "WELD1"]


def test_require_open_refuses_a_day_outside_the_account(owners: OwnerRepository) -> None:
    owners.close("WELD1", date(2024, 6, 30))
    assert owners.require_open("WELD1", date(2024, 6, 30)).code == "WELD1"
    with pytest.raises(NotFoundError, match="was not open"):
        owners.require_open("WELD1", date(2024, 7, 1))


def test_account_rules() -> None:
    with pytest.raises(ValidationError, match="needs a name"):
        OwnerAccount(code="X1", name="  ", opened_on=date(2020, 1, 1))
    with pytest.raises(ValidationError, match="not a thing"):
        OwnerAccount(code="X1", name="X", opened_on=date(2020, 1, 1), terms_days=365)
    with pytest.raises(ValidationError, match="cannot close"):
        OwnerAccount(code="X1", name="X", opened_on=date(2020, 1, 1), closed_on=date(2019, 1, 1))
