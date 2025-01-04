"""Price book and invoicing commands."""

from __future__ import annotations

from datetime import date
from fractions import Fraction

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.errors import NotFoundError
from starstamp.model.contract import ContractTerm
from starstamp.model.dates import StampedMonth, parse_day
from starstamp.model.invoice import Invoice
from starstamp.model.money import Money
from starstamp.model.pricing import PriceItem, normalise_charge_code
from starstamp.service.billing import BillingService
from starstamp.store.contracts import ContractRepository
from starstamp.store.invoices import InvoiceRepository
from starstamp.store.owners import OwnerRepository
from starstamp.store.pricing import PriceRepository
from starstamp.text.table import dash, render_pairs, render_table


@click.group()
def price() -> None:
    """The price book."""


@price.command("set")
@click.argument("code")
@click.argument("amount")
@click.option("--from", "effective_from", default=None, help="the day it starts, YYYY-MM-DD")
@click.option("--description", default=None)
@pass_shop
def set_price(
    shop: ShopContext,
    code: str,
    amount: str,
    effective_from: str | None,
    description: str | None,
) -> None:
    """Open a new price, closing whatever it replaces."""
    wanted = normalise_charge_code(code)
    day = resolve_day(effective_from, shop)
    money = Money.parse(amount)
    with shop.open_for_write() as handle:
        repository = PriceRepository(handle.connection)
        if repository.for_code(wanted):
            item = repository.raise_price(wanted, money, day, description or wanted.lower())
        else:
            item = PriceItem(
                code=wanted,
                description=description or wanted.lower(),
                amount=money,
                effective_from=day,
            )
            repository.add(item)
    click.echo(f"{item.code} is {item.amount.with_symbol()} from {item.effective_from}")


@price.command("list")
@click.option("--on", "day", default=None, help="the day to read prices for")
@click.option("--history", "code", default=None, help="show every price for one code")
@pass_shop
def list_prices(shop: ShopContext, day: str | None, code: str | None) -> None:
    """What the shop charges."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        repository = PriceRepository(handle.connection)
        items = repository.for_code(code) if code else repository.current(when)
    if not items:
        click.echo("no prices on file")
        return
    click.echo(
        render_table(
            ["code", "description", "amount", "from", "until"],
            [
                [
                    item.code,
                    item.description,
                    str(item.amount),
                    item.effective_from.isoformat(),
                    dash(item.effective_until),
                ]
                for item in items
            ],
            right=(2,),
        )
    )


@click.group()
def invoice() -> None:
    """Invoices."""


@invoice.command("draft")
@click.argument("owner")
@click.option("--month", default=None, help="the month to bill, YYYY-MM")
@click.option("--from", "first", default=None)
@click.option("--to", "last", default=None)
@pass_shop
def draft_invoice(
    shop: ShopContext, owner: str, month: str | None, first: str | None, last: str | None
) -> None:
    """Show what an account owes without raising anything."""
    start, end = _window(shop, month, first, last)
    with shop.open() as handle:
        draft = BillingService(handle).draft(owner.upper(), start, end, shop.today)
    _render_invoice(draft.invoice, drafted=True)
    for line in draft.skipped:
        click.echo(f"  left off: {line}")


@invoice.command("raise")
@click.argument("owner")
@click.option("--month", default=None, help="the month to bill, YYYY-MM")
@click.option("--from", "first", default=None)
@click.option("--to", "last", default=None)
@pass_shop
def raise_invoice(
    shop: ShopContext, owner: str, month: str | None, first: str | None, last: str | None
) -> None:
    """Raise an invoice for an account."""
    start, end = _window(shop, month, first, last)
    with shop.open_for_write() as handle:
        written = BillingService(handle).raise_invoice(owner.upper(), start, end, shop.today)
    click.echo(f"raised {written}")


@invoice.command("show")
@click.argument("number")
@pass_shop
def show_invoice(shop: ShopContext, number: str) -> None:
    """Show one invoice."""
    with shop.open() as handle:
        found = InvoiceRepository(handle.connection).by_number(number)
    _render_invoice(found, drafted=False)


@invoice.command("settle")
@click.argument("number")
@click.option("--on", "day", default=None)
@pass_shop
def settle_invoice(shop: ShopContext, number: str, day: str | None) -> None:
    """Mark an invoice paid."""
    when = resolve_day(day, shop)
    with shop.open_for_write() as handle:
        settled = InvoiceRepository(handle.connection).settle(number, when)
    click.echo(f"{settled.number} settled {settled.settled_on}")


@invoice.command("outstanding")
@pass_shop
def outstanding(shop: ShopContext) -> None:
    """Everything unpaid, oldest due date first."""
    with shop.open() as handle:
        found = InvoiceRepository(handle.connection).outstanding()
    if not found:
        click.echo("nothing outstanding")
        return
    click.echo(
        render_table(
            ["invoice", "owner", "raised", "due", "amount", "overdue"],
            [
                [
                    item.number,
                    item.owner_code,
                    item.raised_on.isoformat(),
                    item.due_on.isoformat(),
                    str(item.total),
                    str(item.days_overdue(shop.today)),
                ]
                for item in found
            ],
            right=(4, 5),
        )
    )


def _window(
    shop: ShopContext, month: str | None, first: str | None, last: str | None
) -> tuple[date, date]:
    if month is not None:
        year, _, number = month.partition("-")
        stamped = StampedMonth(int(year), int(number))
        return stamped.first_day(), stamped.last_day()
    if first is None or last is None:
        stamped = StampedMonth.of(shop.today)
        return stamped.first_day(), stamped.last_day()
    return parse_day(first), parse_day(last)


def _render_invoice(found: Invoice, *, drafted: bool) -> None:
    click.echo(
        render_pairs(
            [
                ("invoice", found.number + (" (draft)" if drafted else "")),
                ("account", found.owner_code),
                ("window", f"{found.first_day} to {found.last_day}"),
                ("raised", found.raised_on.isoformat()),
                ("due", found.due_on.isoformat()),
                ("settled", dash(found.settled_on)),
                ("total", found.total.with_symbol()),
            ]
        )
    )
    if found.lines:
        click.echo("")
        click.echo(
            render_table(
                ["date", "code", "cylinder", "count", "unit", "amount"],
                [line.row() for line in found.lines],
                right=(3, 4, 5),
            )
        )


@click.group()
def contract() -> None:
    """Prices agreed with one account."""


@contract.command("agree")
@click.argument("owner")
@click.argument("code")
@click.option("--price", default=None, help="a flat price for this code")
@click.option("--discount", default=None, help="a percentage off the book instead")
@click.option("--from", "effective_from", default=None, help="the day it starts")
@pass_shop
def agree(
    shop: ShopContext,
    owner: str,
    code: str,
    price: str | None,
    discount: str | None,
    effective_from: str | None,
) -> None:
    """Agree a price with an account, closing whatever it replaces."""
    if (price is None) == (discount is None):
        raise click.BadParameter("pass either --price or --discount, not both")
    term = ContractTerm(
        owner_code=owner.upper(),
        code=normalise_charge_code(code),
        effective_from=resolve_day(effective_from, shop),
        amount=None if price is None else Money.parse(price),
        discount_percent=None if discount is None else Fraction(discount.rstrip("%")),
    )
    with shop.open_for_write() as handle:
        owner_id = OwnerRepository(handle.connection).id_of(term.owner_code)
        ContractRepository(handle.connection).agree(term, owner_id)
    click.echo(f"agreed {term} from {term.effective_from}")


@contract.command("show")
@click.argument("owner")
@click.option("--on", "day", default=None, help="the day to read it for")
@click.option("--history", is_flag=True, help="show closed terms too")
@pass_shop
def show_contract(shop: ShopContext, owner: str, day: str | None, history: bool) -> None:
    """What an account has agreed."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        repository = ContractRepository(handle.connection)
        terms = (
            list(repository.contract(owner).terms) if history else repository.current(owner, when)
        )
        book = PriceRepository(handle.connection).book()
    if not terms:
        click.echo(f"{owner.upper()} pays the book price for everything")
        return
    rows = []
    for term in terms:
        try:
            list_price = str(book.amount(term.code, when))
        except NotFoundError:
            list_price = "-"
        rows.append(
            [
                term.code,
                "flat" if term.is_flat else "discount",
                str(term.amount)
                if term.amount is not None
                else f"{float(term.discount_percent or 0):.1f}%",
                list_price,
                term.effective_from.isoformat(),
                dash(term.effective_until),
            ]
        )
    click.echo(
        render_table(["code", "kind", "agreed", "book", "from", "until"], rows, right=(2, 3))
    )


@contract.command("accounts")
@pass_shop
def accounts(shop: ShopContext) -> None:
    """Which accounts have anything agreed."""
    with shop.open() as handle:
        found = ContractRepository(handle.connection).accounts_with_terms()
    if not found:
        click.echo("nothing agreed with anybody")
        return
    for code in found:
        click.echo(code)
