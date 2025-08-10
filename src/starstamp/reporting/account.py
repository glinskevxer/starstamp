"""One account, on one page.

The front counter reads this with the customer on the phone. It is the fleet,
the money and what is in the shop right now, in that order, because that is
the order the questions come in: how many have I got, what do I owe you, and
where is the one I sent last week.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.cylinder import Cylinder
from starstamp.model.money import Money
from starstamp.model.owner import OwnerAccount
from starstamp.reporting import fleet, statement
from starstamp.reporting.aging import bucket_for
from starstamp.store.db import Book
from starstamp.store.lots import LotRepository
from starstamp.store.notices import NoticeRepository
from starstamp.store.owners import OwnerRepository
from starstamp.text.table import render_pairs, render_table


@dataclass(frozen=True)
class AccountPage:
    """Everything about one account that fits on a screen."""

    account: OwnerAccount
    standing: fleet.FleetStanding
    money: statement.Statement
    in_the_shop: tuple[Cylinder, ...]
    open_lots: tuple[str, ...]
    unsent_letters: int
    day: date

    @property
    def owed(self) -> Money:
        return self.money.owed

    @property
    def oldest_bucket(self) -> str:
        if not self.money.outstanding:
            return "current"
        return bucket_for(max(item.days_overdue(self.day) for item in self.money.outstanding))

    def describe(self) -> str:
        return (
            f"{self.account.code} {self.account.name}: {self.standing.size} cylinders, "
            f"{len(self.in_the_shop)} here, {self.owed.with_symbol()} outstanding"
        )


def build(book: Book, owner_code: str, first: date, last: date, day: date) -> AccountPage:
    owners = OwnerRepository(book.connection)
    lots = LotRepository(book.connection)
    notices = NoticeRepository(book.connection)

    account = owners.by_code(owner_code)
    return AccountPage(
        account=account,
        standing=fleet.build(book, account.code, day),
        money=statement.build(book, account.code, first, last, day),
        in_the_shop=tuple(fleet.in_shop(book, account.code)),
        open_lots=tuple(lot.number for lot in lots.for_owner(account.code) if lot.status.is_open),
        unsent_letters=sum(
            1 for notice in notices.for_owner(account.code) if not notice.state.is_sent
        ),
        day=day,
    )


def render(page: AccountPage) -> str:
    account = page.account
    lines = [
        render_pairs(
            [
                ("account", f"{account.code} {account.name}"),
                ("contact", account.contact or "-"),
                ("phone", account.phone or "-"),
                ("terms", f"{account.terms_days} days"),
                ("open since", account.opened_on.isoformat()),
                ("cylinders", str(page.standing.size)),
                ("in the shop", str(len(page.in_the_shop))),
                ("open lots", ", ".join(page.open_lots) or "-"),
                ("outstanding", page.owed.with_symbol()),
                ("oldest", page.oldest_bucket),
                ("letters waiting", str(page.unsent_letters)),
            ]
        )
    ]
    overdue = page.standing.overdue()
    coming = page.standing.due_within(6)
    if overdue or coming:
        lines.append("")
        lines.append(
            render_table(
                ["cylinder", "gas", "due", "months"],
                [
                    [
                        str(row.cylinder.key),
                        row.cylinder.service.code,
                        "-" if row.due is None else str(row.due),
                        "-" if row.months_left is None else str(row.months_left),
                    ]
                    for row in sorted(overdue + coming, key=lambda item: item.months_left or 0)
                ],
                right=(3,),
            )
        )
    if page.in_the_shop:
        lines.append("")
        lines.append(
            render_table(
                ["here now", "spec", "status"],
                [
                    [str(cylinder.key), str(cylinder.specification), cylinder.status.value]
                    for cylinder in page.in_the_shop
                ],
            )
        )
    return "\n".join(lines)
