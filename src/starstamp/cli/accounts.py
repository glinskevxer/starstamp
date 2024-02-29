"""Customer account commands."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.model.dates import parse_day
from starstamp.model.owner import OwnerAccount, normalise_owner_code
from starstamp.store.owners import OwnerRepository
from starstamp.text.table import dash, render_pairs, render_table, yes_no


@click.group()
def account() -> None:
    """Customer accounts."""


@account.command("add")
@click.argument("code")
@click.argument("name")
@click.option("--contact", default=None, help="who to call about this account")
@click.option("--terms", type=int, default=30, show_default=True, help="payment terms in days")
@click.option("--opened", default=None, help="the day the account opened, YYYY-MM-DD")
@pass_shop
def add_account(
    shop: ShopContext,
    code: str,
    name: str,
    contact: str | None,
    terms: int,
    opened: str | None,
) -> None:
    """Open an account."""
    account_record = OwnerAccount(
        code=normalise_owner_code(code),
        name=name,
        opened_on=resolve_day(opened, shop),
        contact=contact,
        terms_days=terms,
    )
    with shop.open_for_write() as handle:
        OwnerRepository(handle.connection).add(account_record)
    click.echo(f"opened {account_record}")


@account.command("show")
@click.argument("code")
@pass_shop
def show_account(shop: ShopContext, code: str) -> None:
    """Show one account."""
    with shop.open() as handle:
        found = OwnerRepository(handle.connection).by_code(code)
    click.echo(
        render_pairs(
            [
                ("code", found.code),
                ("name", found.name),
                ("contact", dash(found.contact)),
                ("terms", f"{found.terms_days} days"),
                ("opened", found.opened_on.isoformat()),
                ("closed", dash(found.closed_on)),
                ("open", yes_no(found.is_open)),
            ]
        )
    )


@account.command("list")
@click.option("--open-only", is_flag=True, help="leave out accounts that have closed")
@pass_shop
def list_accounts(shop: ShopContext, open_only: bool) -> None:
    """List the accounts on the books."""
    with shop.open() as handle:
        found = OwnerRepository(handle.connection).all()
    if open_only:
        found = [item for item in found if item.is_open]
    if not found:
        click.echo("no accounts")
        return
    click.echo(
        render_table(
            ["code", "name", "terms", "opened", "closed"],
            [
                [
                    item.code,
                    item.name,
                    str(item.terms_days),
                    item.opened_on.isoformat(),
                    dash(item.closed_on),
                ]
                for item in found
            ],
            right=(2,),
        )
    )


@account.command("close")
@click.argument("code")
@click.option("--on", "day", default=None, help="the day it closed, YYYY-MM-DD")
@pass_shop
def close_account(shop: ShopContext, code: str, day: str | None) -> None:
    """Close an account."""
    with shop.open_for_write() as handle:
        closed = OwnerRepository(handle.connection).close(code, resolve_day(day, shop))
    click.echo(f"closed {closed.code} on {closed.closed_on}")


@account.command("reopen")
@click.argument("code")
@pass_shop
def reopen_account(shop: ShopContext, code: str) -> None:
    """Reopen a closed account."""
    with shop.open_for_write() as handle:
        reopened = OwnerRepository(handle.connection).reopen(code)
    click.echo(f"reopened {reopened.code}")


@account.command("statement-date")
@click.argument("code")
@click.argument("invoiced")
@pass_shop
def statement_date(shop: ShopContext, code: str, invoiced: str) -> None:
    """Say when an invoice raised on a day falls due under the account terms."""
    with shop.open() as handle:
        found = OwnerRepository(handle.connection).by_code(code)
    raised = parse_day(invoiced)
    from datetime import timedelta

    click.echo((raised + timedelta(days=found.terms_days)).isoformat())
