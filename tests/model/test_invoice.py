from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.invoice import (
    Invoice,
    InvoiceLine,
    due_date,
    format_invoice_number,
    parse_invoice_number,
)
from starstamp.model.money import Money

RAISED = date(2024, 7, 1)


def a_line(**changes: object) -> InvoiceLine:
    base: dict[str, object] = {
        "code": "REQUAL_WJ",
        "description": "water jacket requalification",
        "performed_on": date(2024, 6, 12),
        "unit": Money.parse("14.50"),
        "cylinder_key": "NCI/A4471",
        "event_id": 1,
    }
    base.update(changes)
    return InvoiceLine(**base)  # type: ignore[arg-type]


def an_invoice(**changes: object) -> Invoice:
    base: dict[str, object] = {
        "number": "I2024-0001",
        "owner_code": "WELD1",
        "raised_on": RAISED,
        "due_on": date(2024, 7, 31),
        "first_day": date(2024, 6, 1),
        "last_day": date(2024, 6, 30),
        "lines": (a_line(), a_line(code="HANDLING", unit=Money.parse("5.00"), cylinder_key=None)),
    }
    base.update(changes)
    return Invoice(**base)  # type: ignore[arg-type]


def test_numbers_format_and_parse() -> None:
    assert format_invoice_number(2024, 1) == "I2024-0001"
    assert parse_invoice_number("i2024-0001") == (2024, 1)
    with pytest.raises(ValidationError, match="IYYYY-NNNN"):
        parse_invoice_number("2024-1")
    with pytest.raises(ValidationError, match="1 to 9999"):
        format_invoice_number(2024, 0)


def test_a_line_covers_at_least_one_thing() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        a_line(count=0)


def test_line_amounts_multiply() -> None:
    assert a_line(count=3).amount == Money.parse("43.50")
    assert a_line().row()[0] == "2024-06-12"


def test_the_total_is_the_sum_of_the_lines() -> None:
    assert an_invoice().total == Money.parse("19.50")
    assert an_invoice(lines=()).total == Money.zero()


def test_grouping_by_code() -> None:
    grouped = an_invoice(lines=(a_line(), a_line(), a_line(code="VALVE"))).by_code()
    assert grouped["REQUAL_WJ"] == Money.parse("29.00")
    assert list(grouped) == ["REQUAL_WJ", "VALVE"]


def test_a_backwards_window_is_refused() -> None:
    with pytest.raises(ValidationError, match="ends before it starts"):
        an_invoice(first_day=date(2024, 7, 1), last_day=date(2024, 6, 1))


def test_an_invoice_due_before_it_was_raised() -> None:
    with pytest.raises(ValidationError, match="fall due before"):
        an_invoice(due_on=date(2024, 6, 1))


def test_settled_before_it_was_raised() -> None:
    with pytest.raises(ValidationError, match="settled before"):
        an_invoice(settled_on=date(2024, 6, 1))


def test_overdue_counts_only_while_unpaid() -> None:
    invoice = an_invoice()
    assert not invoice.is_overdue(date(2024, 7, 31))
    assert invoice.is_overdue(date(2024, 8, 1))
    assert invoice.days_overdue(date(2024, 8, 15)) == 15
    settled = an_invoice(settled_on=date(2024, 7, 20))
    assert settled.is_settled
    assert not settled.is_overdue(date(2024, 9, 1))
    assert settled.days_overdue(date(2024, 9, 1)) == 0


def test_due_dates_come_off_the_terms() -> None:
    assert due_date(RAISED, 30) == date(2024, 7, 31)
    assert due_date(RAISED, 0) == RAISED


def test_text_form() -> None:
    assert str(an_invoice()) == "I2024-0001 WELD1 $19.50"
