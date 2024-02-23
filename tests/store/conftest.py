from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from starstamp.model.owner import OwnerAccount
from starstamp.store.db import Book, open_book
from starstamp.store.migrations import migrate
from starstamp.store.owners import OwnerRepository


@pytest.fixture
def book(tmp_path: Path) -> Iterator[Book]:
    handle = open_book(tmp_path / "shop.sqlite3")
    with handle:
        migrate(handle.connection)
        yield handle


@pytest.fixture
def owners(book: Book) -> OwnerRepository:
    repository = OwnerRepository(book.connection)
    repository.add(
        OwnerAccount(code="WELD1", name="Cascade Welding Supply", opened_on=date(2019, 4, 1))
    )
    return repository
