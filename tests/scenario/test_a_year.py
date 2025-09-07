"""A year of a small shop, read back through the reports at the end of it.

The other scenario walks one cylinder. This one runs a shop: forty cylinders,
a month of bench work, invoices raised and half paid, condemnations written
about and dealt with. What it asserts is that the reports agree with each
other, because a shop that has to reconcile two of its own reports by hand
does not trust either.
"""

from __future__ import annotations

from datetime import date

import pytest

from starstamp.model.dates import StampedMonth
from starstamp.model.money import Money
from starstamp.reporting import aging, close, condemnation, throughput, unbilled
from starstamp.service.billing import BillingService
from starstamp.service.demo import seed
from starstamp.service.doctor import Doctor
from starstamp.service.worklist import WorklistService
from starstamp.store.db import Book, open_book
from starstamp.store.migrations import migrate

TODAY = date(2025, 6, 8)
MONTH = StampedMonth(2025, 6)


@pytest.fixture
def a_year(tmp_path: object) -> Book:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    handle = open_book(tmp_path / "year.sqlite3")
    handle.__enter__()
    migrate(handle.connection)
    seed(handle, TODAY, cylinders=40)
    return handle


def test_the_throughput_and_the_close_agree(a_year: Book) -> None:
    events = throughput.standing_between(a_year, MONTH.first_day(), MONTH.last_day())
    tally = throughput.overall(events)
    pack = close.build(a_year, MONTH, TODAY)
    assert pack.tally.passed == tally.passed
    assert pack.tally.condemned == tally.condemned
    assert pack.worked == tally.total


def test_the_condemnations_agree_with_the_throughput(a_year: Book) -> None:
    events = throughput.standing_between(a_year, MONTH.first_day(), MONTH.last_day())
    analysis = condemnation.build(a_year, MONTH.first_day(), MONTH.last_day())
    assert analysis.count == throughput.overall(events).condemned


def test_the_unbilled_work_turns_into_an_invoice(a_year: Book) -> None:
    before = unbilled.build(a_year, TODAY)
    assert before.events
    BillingService(a_year).raise_invoice("WELD1", MONTH.first_day(), MONTH.last_day(), TODAY)
    after = unbilled.build(a_year, TODAY)
    assert len(after.events) < len(before.events)
    owed = aging.build(a_year, TODAY)
    assert owed.outstanding > Money.zero()


def test_the_invoice_and_the_close_agree(a_year: Book) -> None:
    invoice = BillingService(a_year).raise_invoice(
        "WELD1", MONTH.first_day(), MONTH.last_day(), TODAY
    )
    pack = close.build(a_year, MONTH, TODAY)
    assert pack.invoiced == invoice.total
    assert pack.outstanding == invoice.total


def test_paying_it_moves_the_money_and_nothing_else(a_year: Book) -> None:
    service = BillingService(a_year)
    invoice = service.raise_invoice("WELD1", MONTH.first_day(), MONTH.last_day(), TODAY)
    service.invoices.settle(invoice.number, TODAY)
    pack = close.build(a_year, MONTH, TODAY)
    assert pack.settled == invoice.total
    assert pack.outstanding == Money.zero()
    assert pack.worked > 0


def test_the_worklist_shrinks_as_the_shop_works(a_year: Book) -> None:
    service = WorklistService(a_year)
    before = unbilled.build(a_year, TODAY).value
    assert service.build(TODAY).of_kind("unbilled")
    BillingService(a_year).raise_invoice("WELD1", MONTH.first_day(), MONTH.last_day(), TODAY)
    after = unbilled.build(a_year, TODAY).value
    assert after < before
    remaining = service.build(TODAY).of_kind("unbilled")
    # The other account's work is still there, which is the point: billing one
    # customer does not clear the list.
    assert remaining


def test_the_book_stays_sound_through_all_of_it(a_year: Book) -> None:
    BillingService(a_year).raise_invoice("WELD1", MONTH.first_day(), MONTH.last_day(), TODAY)
    report = Doctor(a_year).run(TODAY)
    assert report.is_clean, report.describe()
