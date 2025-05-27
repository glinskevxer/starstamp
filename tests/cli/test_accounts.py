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


def test_details_are_kept(shop: Invoke) -> None:
    shop(
        "account",
        "add",
        "weld1",
        "Cascade Welding Supply",
        "--address",
        "1400 S Gladiola St, Salt Lake City UT",
        "--phone",
        "801 555 0134",
        "--email",
        "ruth@example.com",
    )
    out = shop("account", "show", "weld1").output
    assert "1400 S Gladiola St" in out
    assert "801 555 0134" in out
    assert "ruth@example.com" in out


def test_changing_the_details(shop: Invoke) -> None:
    shop("account", "add", "weld1", "Cascade")
    shop("account", "details", "weld1", "--phone", "801 555 0134")
    assert "801 555 0134" in shop("account", "show", "weld1").output
    shop("account", "details", "weld1", expect=2)


def test_who_the_shop_cannot_write_to(shop: Invoke) -> None:
    shop("account", "add", "weld1", "Cascade")
    assert "WELD1 Cascade" in shop("account", "unreachable").output
    shop("account", "details", "weld1", "--address", "1400 S Gladiola St")
    assert "every open account can be written to" in shop("account", "unreachable").output


def test_the_letterhead(shop: Invoke) -> None:
    shop(
        "account",
        "add",
        "weld1",
        "Cascade Welding Supply",
        "--contact",
        "Ruth Alvarez",
        "--address",
        "1400 S Gladiola St, Salt Lake City UT 84104",
    )
    out = shop("account", "letterhead", "weld1").output
    assert "attn Ruth Alvarez" in out
    assert "Salt Lake City UT 84104" in out


def test_a_bad_email_is_refused(shop: Invoke) -> None:
    shop("account", "add", "weld1", "Cascade", "--email", "ruth at example", expect=2)
