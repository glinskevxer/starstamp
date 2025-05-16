"""What the store does when something goes wrong halfway through.

The service layer wraps most of its work in one transaction, so the question
that matters is not whether a write works but whether a failed write leaves
the book in a state somebody has to unpick by hand. These tests break things
on purpose in the middle.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from starstamp.errors import ConflictError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.lot import Lot
from starstamp.model.owner import OwnerAccount
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book, open_book, transaction
from starstamp.store.lots import LotRepository
from starstamp.store.migrations import migrate
from starstamp.store.owners import OwnerRepository

from ..support.factories import make_cylinder

KEY = CylinderKey("NCI", "A4471")


def test_a_failed_unit_of_work_leaves_nothing_behind(book: Book, owners: OwnerRepository) -> None:
    def half_a_day() -> None:
        with transaction(book.connection):
            owners.add(OwnerAccount(code="FIRE7", name="Sanpete", opened_on=date(2020, 1, 1)))
            raise RuntimeError("the power went out")

    with pytest.raises(RuntimeError):
        half_a_day()
    assert [item.code for item in owners.all()] == ["WELD1"]


def test_a_conflict_inside_a_transaction_rolls_the_lot_back(
    book: Book, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    def take_two_in() -> None:
        with transaction(book.connection):
            cylinders.add(make_cylinder(key=KEY), owners.id_of("WELD1"), date(2024, 1, 2))
            cylinders.add(make_cylinder(key=KEY), owners.id_of("WELD1"), date(2024, 1, 2))

    with pytest.raises(ConflictError):
        take_two_in()
    assert cylinders.count() == 0


def test_a_reference_to_nothing_is_refused(book: Book) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        book.connection.execute(
            "INSERT INTO lot (number, owner_id, received_on)"
            " VALUES ('L2024-0001', 4242, '2024-06-03')"
        )


def test_a_row_cannot_be_orphaned_by_a_delete(
    book: Book, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    cylinders.add(make_cylinder(key=KEY), owners.id_of("WELD1"), date(2024, 1, 2))
    with pytest.raises(sqlite3.IntegrityError):
        book.connection.execute("DELETE FROM owner_account WHERE code = 'WELD1'")


def test_two_connections_see_each_other_after_a_commit(tmp_path: Path) -> None:
    path = tmp_path / "shop.sqlite3"
    with open_book(path) as first:
        migrate(first.connection)
        with first.write():
            OwnerRepository(first.connection).add(
                OwnerAccount(code="WELD1", name="Cascade", opened_on=date(2019, 4, 1))
            )
        with open_book(path) as second:
            assert [item.code for item in OwnerRepository(second.connection).all()] == ["WELD1"]


def test_a_second_connection_does_not_see_an_open_transaction(tmp_path: Path) -> None:
    path = tmp_path / "shop.sqlite3"
    with open_book(path) as first:
        migrate(first.connection)
        first.connection.execute("BEGIN IMMEDIATE")
        OwnerRepository(first.connection).add(
            OwnerAccount(code="WELD1", name="Cascade", opened_on=date(2019, 4, 1))
        )
        with open_book(path) as second:
            assert OwnerRepository(second.connection).all() == []
        first.connection.execute("ROLLBACK")


def test_a_lot_line_needs_both_ends(
    book: Book, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    lots = LotRepository(book.connection)
    lots.add(
        Lot(number="L2024-0001", owner_code="WELD1", received_on=date(2024, 6, 3)),
        owners.id_of("WELD1"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        book.connection.execute(
            "INSERT INTO lot_line (lot_id, cylinder_id, added_on) VALUES (?, 999, '2024-06-03')",
            (lots.id_of("L2024-0001"),),
        )


def test_the_book_is_in_write_ahead_mode(book: Book) -> None:
    assert book.connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_rows_come_back_by_name_everywhere(book: Book) -> None:
    row = book.connection.execute("SELECT 1 AS one, 2 AS two").fetchone()
    assert row["one"] == 1
    assert row["two"] == 2
