from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner

from starstamp.cli.context import ShopContext
from starstamp.cli.main import cli, exit_code_for, run
from starstamp.errors import (
    ConflictError,
    NotFoundError,
    RuleViolationError,
    StarstampError,
    ValidationError,
)

from .conftest import Invoke


def test_init_applies_the_migrations(run: Invoke, book_path: Path) -> None:
    result = run("init")
    assert "applied 0001_core" in result.output
    assert book_path.exists()


def test_init_twice_is_quiet(run: Invoke) -> None:
    run("init")
    assert "already current" in run("init").output


def test_about_before_init(run: Invoke) -> None:
    assert "no book yet" in run("about").output


def test_about_after_init(shop: Invoke) -> None:
    output = shop("about").output
    assert "schema version" in output
    assert "0 cylinders" in output


def test_opening_a_missing_book_is_refused(tmp_path: Path) -> None:
    shop = ShopContext(book_path=tmp_path / "missing.sqlite3", today=date(2024, 1, 1))

    def act() -> None:
        with shop.open():
            pass

    with pytest.raises(NotFoundError, match="run starstamp init first"):
        act()


def test_opening_a_book_with_no_schema_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "empty.sqlite3"
    path.touch()
    shop = ShopContext(book_path=path, today=date(2024, 1, 1))

    def act() -> None:
        with shop.open():
            pass

    with pytest.raises(NotFoundError, match="no schema"):
        act()


def test_version_is_reported() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "starstamp" in result.output


def test_the_entry_point_returns_zero_on_a_good_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    book = tmp_path / "shop.sqlite3"
    monkeypatch.setattr("sys.argv", ["starstamp", "--book", str(book), "init"])
    assert run() == 0
    assert book.exists()


def test_the_entry_point_reports_a_file_that_is_not_a_book(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    junk = tmp_path / "packing-slip.sqlite3"
    junk.write_text("not a book at all\n")
    monkeypatch.setattr("sys.argv", ["starstamp", "--book", str(junk), "about"])
    assert run() == 1
    assert "not a usable book" in capsys.readouterr().err


def test_the_entry_point_maps_a_missing_record_to_three(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    book = tmp_path / "shop.sqlite3"
    book.touch()
    monkeypatch.setattr("sys.argv", ["starstamp", "--book", str(book), "about"])
    assert run() == 3
    assert "no schema" in capsys.readouterr().err


def test_a_bad_option_is_a_click_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["starstamp", "--today", "yesterday", "init"])
    assert run() == 2


def test_today_can_be_pinned(shop: Invoke) -> None:
    result = shop("--today", "2024-05-04", "about")
    assert result.exit_code == 0


def test_domain_errors_become_exit_codes() -> None:
    assert exit_code_for(ValidationError("bad")) == 2
    assert exit_code_for(NotFoundError("gone")) == 3
    assert exit_code_for(ConflictError("twice")) == 4
    assert exit_code_for(RuleViolationError("no", "180.205")) == 5
    assert exit_code_for(StarstampError("something else")) == 1


def test_the_error_is_printed_with_a_prefix(book_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--book", str(book_path), "account", "show", "nope"])
    assert result.exit_code == 3
    assert "error: no book" in result.output
