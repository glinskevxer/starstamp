"""The customer account, and whether the shop could write to it."""

from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.owner import OwnerAccount


def test_an_account_with_nowhere_to_write_to() -> None:
    account = OwnerAccount(code="WELD1", name="Cascade", opened_on=date(2019, 4, 1))
    assert not account.can_be_written_to
    with_post = OwnerAccount(
        code="WELD1",
        name="Cascade",
        opened_on=date(2019, 4, 1),
        address="1400 S Gladiola St, Salt Lake City UT",
    )
    assert with_post.can_be_written_to
    by_email = OwnerAccount(
        code="WELD1",
        name="Cascade",
        opened_on=date(2019, 4, 1),
        email="ruth@example.com",
    )
    assert by_email.can_be_written_to


def test_an_email_that_is_not_one() -> None:
    with pytest.raises(ValidationError, match="not an email address"):
        OwnerAccount(
            code="WELD1", name="Cascade", opened_on=date(2019, 4, 1), email="ruth at example"
        )


def test_the_postal_block() -> None:
    account = OwnerAccount(
        code="WELD1",
        name="Cascade Welding Supply",
        opened_on=date(2019, 4, 1),
        contact="Ruth Alvarez",
        address="1400 S Gladiola St, Salt Lake City UT 84104",
    )
    block = account.postal_block().splitlines()
    assert block == [
        "Cascade Welding Supply",
        "attn Ruth Alvarez",
        "1400 S Gladiola St",
        "Salt Lake City UT 84104",
    ]


def test_a_postal_block_with_only_a_name() -> None:
    account = OwnerAccount(code="WELD1", name="Cascade", opened_on=date(2019, 4, 1))
    assert account.postal_block() == "Cascade"
