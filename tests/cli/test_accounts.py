from .conftest import Invoke


def test_add_and_show(shop: Invoke) -> None:
    shop("account", "add", "weld1", "Cascade Welding Supply", "--contact", "Ruth")
    out = shop("account", "show", "WELD1").output
    assert "Cascade Welding Supply" in out
    assert "Ruth" in out
    assert "terms    30 days" in out


def test_add_refuses_a_duplicate(shop: Invoke) -> None:
    shop("account", "add", "weld1", "Cascade")
    shop("account", "add", "weld1", "Cascade again", expect=4)


def test_list_is_empty_at_first(shop: Invoke) -> None:
    assert "no accounts" in shop("account", "list").output


def test_list_shows_what_is_there(shop: Invoke) -> None:
    shop("account", "add", "weld1", "Cascade", "--opened", "2020-02-03")
    shop("account", "add", "fire7", "Sanpete Fire", "--terms", "45")
    out = shop("account", "list").output
    assert "FIRE7" in out
    assert "WELD1" in out
    assert "2020-02-03" in out


def test_close_and_reopen(shop: Invoke) -> None:
    shop("account", "add", "weld1", "Cascade", "--opened", "2020-02-03")
    assert "closed WELD1" in shop("account", "close", "weld1", "--on", "2024-06-30").output
    assert "WELD1" not in shop("account", "list", "--open-only").output
    assert "reopened WELD1" in shop("account", "reopen", "weld1").output


def test_show_a_missing_account(shop: Invoke) -> None:
    shop("account", "show", "nope", expect=3)


def test_statement_date_uses_the_account_terms(shop: Invoke) -> None:
    shop("account", "add", "weld1", "Cascade", "--terms", "45")
    assert shop("account", "statement-date", "weld1", "2024-03-01").output.strip() == "2024-04-15"
