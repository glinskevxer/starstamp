from pathlib import Path

from .conftest import Invoke


def test_backing_up_to_a_named_file(running_shop: Invoke, tmp_path: Path) -> None:
    target = tmp_path / "copy.sqlite3"
    out = running_shop("backup", str(target)).output
    assert "written" in out
    assert target.exists()


def test_a_backup_names_itself_by_default(running_shop: Invoke, book_path: Path) -> None:
    running_shop("backup")
    copies = list(book_path.parent.glob("shop-*.sqlite3"))
    assert len(copies) == 1


def test_a_backup_will_not_clobber(running_shop: Invoke, tmp_path: Path) -> None:
    target = tmp_path / "copy.sqlite3"
    running_shop("backup", str(target))
    running_shop("backup", str(target), expect=4)
    running_shop("backup", str(target), "--overwrite")


def test_verifying_a_healthy_book(running_shop: Invoke) -> None:
    out = running_shop("verify").output
    assert "integrity          ok" in out
    assert "broken references  0" in out


def test_verifying_a_book_behind_the_code(running_shop: Invoke, book_path: Path) -> None:
    import sqlite3

    connection = sqlite3.connect(book_path)
    connection.execute("DELETE FROM schema_migration WHERE number > 3")
    connection.commit()
    connection.close()
    result = running_shop("verify", expect=9)
    assert "schema             3 of" in result.output


def test_vacuuming(running_shop: Invoke) -> None:
    assert "bytes given back" in running_shop("vacuum").output


def test_restoring_over_the_book(running_shop: Invoke, tmp_path: Path, book_path: Path) -> None:
    target = tmp_path / "copy.sqlite3"
    running_shop("backup", str(target))
    running_shop("restore", str(target), expect=4)
    out = running_shop("restore", str(target), "--overwrite").output
    assert f"restored {target}" in out
    assert "NCI/A4471" in running_shop("cylinder", "list").output
