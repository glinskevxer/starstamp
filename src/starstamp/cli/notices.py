"""Commands for the letters that go out to owners."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.service.notices import NoticeService
from starstamp.store.notices import NoticeRepository
from starstamp.text.table import dash, render_table


@click.group()
def notice() -> None:
    """Letters to owners."""


@notice.command("draft")
@click.option("--reminders", is_flag=True, help="also draft due and out of test reminders")
@click.option("--within", default=3, show_default=True, help="months ahead for reminders")
@click.option("--owner", default=None, help="only this account")
@click.option("--on", "day", default=None)
@pass_shop
def draft(
    shop: ShopContext, reminders: bool, within: int, owner: str | None, day: str | None
) -> None:
    """Draft everything the shop owes."""
    when = resolve_day(day, shop)
    with shop.open_for_write() as handle:
        service = NoticeService(handle)
        drafted = service.draft_condemnations(when)
        click.echo(drafted.describe())
        if reminders:
            more = service.draft_reminders(
                when, within, owner_code=None if owner is None else owner.upper()
            )
            click.echo(more.describe())


@notice.command("list")
@click.option("--owner", default=None, help="only this account")
@click.option("--unsent", is_flag=True, help="only the ones still to go out")
@pass_shop
def list_notices(shop: ShopContext, owner: str | None, unsent: bool) -> None:
    """What has been written and what has gone out."""
    with shop.open() as handle:
        repository = NoticeRepository(handle.connection)
        found = repository.unsent() if unsent else []
        if owner is not None:
            found = repository.for_owner(owner)
        elif not unsent:
            found = repository.unsent()
    if not found:
        click.echo("no notices")
        return
    click.echo(
        render_table(
            ["id", "owner", "cylinder", "kind", "raised", "sent", "due"],
            [
                [
                    str(item.notice_id),
                    item.owner_code,
                    item.cylinder_key,
                    item.kind.label,
                    item.raised_on.isoformat(),
                    dash(item.sent_on),
                    dash(item.due_by()),
                ]
                for item in found
            ],
        )
    )


@notice.command("show")
@click.argument("notice_id", type=int)
@pass_shop
def show(shop: ShopContext, notice_id: int) -> None:
    """Print one letter."""
    with shop.open() as handle:
        found = NoticeRepository(handle.connection).by_id(notice_id)
    click.echo(f"To: {found.owner_code}")
    click.echo(f"Date: {found.raised_on.isoformat()}")
    click.echo(f"Subject: {found.kind.label}, cylinder {found.cylinder_key}")
    click.echo("")
    click.echo(found.body)


@notice.command("send")
@click.argument("notice_id", type=int)
@click.option("--on", "day", default=None)
@pass_shop
def send(shop: ShopContext, notice_id: int, day: str | None) -> None:
    """Mark a letter as gone out."""
    when = resolve_day(day, shop)
    with shop.open_for_write() as handle:
        sent = NoticeService(handle).send(notice_id, when)
    click.echo(f"notice {notice_id} sent {sent.sent_on}")


@notice.command("late")
@click.option("--on", "day", default=None)
@pass_shop
def late(shop: ShopContext, day: str | None) -> None:
    """Condemnation letters the shop is past the deadline on."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        found = NoticeService(handle).overdue_letters(when)
    if not found:
        click.echo("nothing late")
        return
    for item in found:
        click.echo(f"{item.summary()}, due {item.due_by()}")
