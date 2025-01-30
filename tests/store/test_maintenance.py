from datetime import datetime
from pathlib import Path

import pytest

from starstamp.errors import ConflictError, StarstampError
from starstamp.store import maintenance
from starstamp.store.db import Book, open_book
from starstamp.store.migrations import migrate


def test_a_backup_is_a_working_book(shop_book: Book, tmp_path: Path) -> None:
    target = tmp_path / "backups" / "shop.sqlite3"
    result = maintenance.backup(shop_book, target)
    assert target.exists()
    assert result.bytes_written > 0
    assert result.pages > 0
    assert "written" in result.describe()
    with open_book(target) as copy:
        assert copy.connection.execute("SELECT count(*) FROM cylinder").fetchone()[0] == 1


def test_a_backup_will_not_clobber_by_accident(shop_book: Book, tmp_path: Path) -> None:
    target = tmp_path / "shop-copy.sqlite3"
    maintenance.backup(shop_book, target)
    with pytest.raises(ConflictError, match="already there"):
        maintenance.backup(shop_book, target)
    maintenance.backup(shop_book, target, overwrite=True)


def test_the_default_backup_name_carries_the_moment() -> None:
    name = maintenance.timestamped_name(
        Path("/shop/book.sqlite3"), datetime(2024, 6, 12, 8, 30, 15)
    )
    assert name.name == "book-20240612-083015.sqlite3"


def test_a_healthy_book_verifies(shop_book: Book) -> None:
    result = maintenance.verify(shop_book)
    assert result.is_sound
    assert result.integrity == "ok"
    assert result.schema == result.expected_schema
    assert "integrity ok" in result.describe()


def test_a_book_behind_the_code_does_not_verify(shop_book: Book) -> None:
    shop_book.connection.execute("DELETE FROM schema_migration WHERE number > 3")
    result = maintenance.verify(shop_book)
    assert not result.is_sound
    assert "schema 3 of" in result.describe()


def test_a_broken_reference_shows_up(shop_book: Book, tmp_path: Path) -> None:
    shop_book.connection.execute("PRAGMA foreign_keys = OFF")
    shop_book.connection.execute(
        "INSERT INTO lot (number, owner_id, received_on) VALUES ('L2024-0009', 999, '2024-06-03')"
    )
    result = maintenance.verify(shop_book)
    assert result.foreign_keys_broken == 1
    assert not result.is_sound
    assert "point at something that is not there" in result.describe()


def test_vacuum_gives_space_back(tmp_path: Path) -> None:
    path = tmp_path / "shop.sqlite3"
    with open_book(path) as handle:
        migrate(handle.connection)
        handle.connection.execute("CREATE TABLE junk (a TEXT)")
        for _index in range(2000):
            handle.connection.execute("INSERT INTO junk VALUES (?)", ("x" * 200,))
        handle.connection.execute("DROP TABLE junk")
        assert maintenance.vacuum(handle) > 0


def test_restoring_a_backup(shop_book: Book, tmp_path: Path) -> None:
    backup = tmp_path / "backup.sqlite3"
    maintenance.backup(shop_book, backup)
    restored = tmp_path / "restored.sqlite3"
    maintenance.restore(backup, restored)
    with open_book(restored) as copy:
        assert copy.connection.execute("SELECT count(*) FROM cylinder").fetchone()[0] == 1


def test_restoring_something_that_is_not_a_backup(tmp_path: Path) -> None:
    missing = tmp_path / "nope.sqlite3"
    with pytest.raises(StarstampError, match="no backup at"):
        maintenance.restore(missing, tmp_path / "out.sqlite3")
    empty = tmp_path / "empty.sqlite3"
    with open_book(empty):
        pass
    with pytest.raises(StarstampError, match="not a book"):
        maintenance.restore(empty, tmp_path / "out.sqlite3")


def test_restoring_over_something(shop_book: Book, tmp_path: Path) -> None:
    backup = tmp_path / "backup.sqlite3"
    maintenance.backup(shop_book, backup)
    target = tmp_path / "target.sqlite3"
    target.write_text("")
    with pytest.raises(ConflictError, match="already there"):
        maintenance.restore(backup, target)
    maintenance.restore(backup, target, overwrite=True)
