import pytest

from .conftest import DAY, Invoke


@pytest.fixture
def priced(running_shop: Invoke) -> Invoke:
    for code, amount, description in (
        ("REQUAL_WJ", "14.50", "water jacket requalification"),
        ("CONDEMN", "9.00", "condemnation and disposal"),
        ("HANDLING", "5.00", "lot handling"),
    ):
        running_shop(
            "price", "set", code, amount, "--from", "2023-01-01", "--description", description
        )
    running_shop(
        "requal",
        "run",
        "NCI/A4471",
        "--tech",
        "jt7",
        "--system",
        "WJ-1",
        "--on",
        DAY,
        "--applied",
        "3358",
        "--total",
        "110.0",
        "--permanent",
        "2.0",
    )
    return running_shop


def test_prices_list(priced: Invoke) -> None:
    out = priced("--today", "2024-06-12", "price", "list").output
    assert "REQUAL_WJ" in out
    assert "14.50" in out


def test_raising_a_price_keeps_the_old_one(priced: Invoke) -> None:
    priced("price", "set", "requal-wj", "16.00", "--from", "2025-01-01")
    history = priced("price", "list", "--history", "REQUAL_WJ").output
    assert "2024-12-31" in history
    assert "16.00" in history


def test_no_prices_at_all(running_shop: Invoke) -> None:
    assert "no prices on file" in running_shop("price", "list").output


def test_a_draft_shows_the_lines(priced: Invoke) -> None:
    out = priced("--today", "2024-07-01", "invoice", "draft", "weld1", "--month", "2024-06").output
    assert "(draft)" in out
    assert "REQUAL_WJ" in out
    assert "total    $14.50" in out


def test_raising_and_showing(priced: Invoke) -> None:
    raised = priced(
        "--today", "2024-07-01", "invoice", "raise", "weld1", "--month", "2024-06"
    ).output
    assert "raised I2024-0001 WELD1 $14.50" in raised
    shown = priced("invoice", "show", "i2024-0001").output
    assert "2024-06-01 to 2024-06-30" in shown
    assert "NCI/A4471" in shown


def test_settling_and_outstanding(priced: Invoke) -> None:
    priced("--today", "2024-07-01", "invoice", "raise", "weld1", "--month", "2024-06")
    out = priced("--today", "2024-09-01", "invoice", "outstanding").output
    assert "I2024-0001" in out
    priced("invoice", "settle", "I2024-0001", "--on", "2024-08-05")
    assert "nothing outstanding" in priced("invoice", "outstanding").output


def test_billing_a_window_with_nothing_in_it(priced: Invoke) -> None:
    priced("--today", "2024-07-01", "invoice", "raise", "weld1", "--month", "2023-06", expect=4)


def test_the_window_defaults_to_this_month(priced: Invoke) -> None:
    out = priced("--today", "2024-06-30", "invoice", "draft", "weld1").output
    assert "2024-06-01 to 2024-06-30" in out


def test_agreeing_a_flat_price(priced: Invoke) -> None:
    out = priced(
        "contract", "agree", "weld1", "requal-wj", "--price", "12.00", "--from", "2023-01-01"
    ).output
    assert "agreed WELD1 REQUAL_WJ at $12.00" in out
    draft = priced(
        "--today", "2024-07-01", "invoice", "draft", "weld1", "--month", "2024-06"
    ).output
    assert "total    $12.00" in draft


def test_agreeing_a_discount(priced: Invoke) -> None:
    priced("contract", "agree", "weld1", "REQUAL_WJ", "--discount", "10", "--from", "2023-01-01")
    out = priced("--today", "2024-06-12", "contract", "show", "weld1").output
    assert "discount" in out
    assert "10.0%" in out
    assert "14.50" in out


def test_a_term_needs_one_of_the_two(priced: Invoke) -> None:
    priced("contract", "agree", "weld1", "REQUAL_WJ", expect=2)
    priced(
        "contract",
        "agree",
        "weld1",
        "REQUAL_WJ",
        "--price",
        "12.00",
        "--discount",
        "10",
        expect=2,
    )


def test_an_account_with_nothing_agreed(priced: Invoke) -> None:
    assert "pays the book price" in priced("contract", "show", "weld1").output
    assert "nothing agreed with anybody" in priced("contract", "accounts").output


def test_the_history_shows_closed_terms(priced: Invoke) -> None:
    priced("contract", "agree", "weld1", "REQUAL_WJ", "--price", "12.00", "--from", "2023-01-01")
    priced("contract", "agree", "weld1", "REQUAL_WJ", "--price", "13.00", "--from", "2025-01-01")
    out = priced("contract", "show", "weld1", "--history").output
    assert "2024-12-31" in out
    assert "13.00" in out
    assert "WELD1" in priced("contract", "accounts").output


def test_the_statement(priced: Invoke) -> None:
    priced("--today", "2024-07-01", "invoice", "raise", "weld1", "--month", "2024-06")
    out = priced(
        "--today", "2024-08-15", "invoice", "statement", "weld1", "--month", "2024-07"
    ).output
    assert "WELD1 Cascade Welding Supply" in out
    assert "invoiced     $14.50" in out
    assert "outstanding  $14.50" in out
    assert "I2024-0001" in out


def test_the_statement_counts_the_work(priced: Invoke) -> None:
    out = priced(
        "--today", "2024-08-15", "invoice", "statement", "weld1", "--month", "2024-06"
    ).output
    assert "requalified  1" in out
    assert "condemned    0" in out


def test_the_aging_report(priced: Invoke) -> None:
    priced("--today", "2024-07-01", "invoice", "raise", "weld1", "--month", "2024-06")
    out = priced("--today", "2024-09-15", "invoice", "aging").output
    assert "WELD1" in out
    assert "31 to 60" in out
    assert "outstanding across 1 accounts" in out


def test_the_aging_report_with_nothing_owed(priced: Invoke) -> None:
    assert "nothing outstanding" in priced("invoice", "aging").output
