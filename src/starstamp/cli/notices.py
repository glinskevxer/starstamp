"""Commands for the letters that go out to owners."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.cli.output import echo_lines, echo_table
from starstamp.model.notice import NoticeKind
from starstamp.service.notices import NoticeService
from starstamp.store.facility import FacilityRepository
from starstamp.store.notices import NoticeRepository
from starstamp.store.owners import OwnerRepository
from starstamp.text.table import dash


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
    echo_table(
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
        empty="no notices",
    )


@notice.command("show")
@click.argument("notice_id", type=int)
@pass_shop
def show(shop: ShopContext, notice_id: int) -> None:
    """Print one letter."""
    with shop.open() as handle:
        found = NoticeRepository(handle.connection).by_id(notice_id)
        account = OwnerRepository(handle.connection).by_code(found.owner_code)
        facility = FacilityRepository(handle.connection).only()
    click.echo(str(facility))
    if facility.address:
        click.echo(facility.address)
    click.echo("")
    click.echo("To:")
    click.echo(account.postal_block())
    click.echo("")
    click.echo(f"Date: {found.raised_on.isoformat()}")
    click.echo(f"Subject: {found.kind.label}, cylinder {found.cylinder_key}")
    click.echo("")
    click.echo(found.body)
    if not account.can_be_written_to:
        click.echo("")
        click.echo("this account has no address on file, so this cannot be posted")


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
    echo_lines((f"{item.summary()}, due {item.due_by()}" for item in found), empty="nothing late")


@notice.command("send-all")
@click.option("--on", "day", default=None, help="the day they went out")
@click.option("--kind", default=None, help="only this kind of letter")
@click.option("--dry-run", is_flag=True, help="list what would go and send nothing")
@pass_shop
def send_all(shop: ShopContext, day: str | None, kind: str | None, dry_run: bool) -> None:
    """Send every letter that is still waiting.

    The shop prints a stack, signs them and posts them, and then wants one
    command rather than one per letter. A letter to an account with no address
    is left where it is and named, because marking it sent would be a lie.
    """
    when = resolve_day(day, shop)
    wanted = None if kind is None else NoticeKind(kind.strip().lower().replace(" ", "_"))
    with shop.open() as handle:
        waiting = [
            item
            for item in NoticeRepository(handle.connection).unsent()
            if wanted is None or item.kind is wanted
        ]
        owners = OwnerRepository(handle.connection)
        reachable = {
            item.notice_id: owners.by_code(item.owner_code).can_be_written_to for item in waiting
        }
    if not waiting:
        click.echo("nothing waiting to go out")
        return
    if dry_run:
        for item in waiting:
            mark = "" if reachable[item.notice_id] else "  (no address)"
            click.echo(f"{item.summary()}{mark}")
        click.echo(f"{len(waiting)} letters would go")
        return

    sent = 0
    with shop.open_for_write() as handle:
        service = NoticeService(handle)
        for item in waiting:
            if item.notice_id is None or not reachable[item.notice_id]:
                continue
            service.send(item.notice_id, when)
            sent += 1
    click.echo(f"{sent} letters sent")
    held = [item for item in waiting if not reachable[item.notice_id]]
    for item in held:
        click.echo(f"  held: {item.owner_code} has no address on file")
