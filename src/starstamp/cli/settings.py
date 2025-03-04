"""Commands for the shop's own numbers."""

from __future__ import annotations

import click

from starstamp.cli.context import ShopContext, pass_shop, resolve_day
from starstamp.model.settings import DEFAULTS, known_settings
from starstamp.store.settings import SettingRepository
from starstamp.text.table import render_table


@click.group("setting")
def setting() -> None:
    """Numbers the shop sets for itself."""


@setting.command("set")
@click.argument("name")
@click.argument("value")
@click.option("--from", "effective_from", default=None, help="the day it takes effect")
@click.option("--by", "set_by", default=None, help="who set it")
@pass_shop
def set_setting(
    shop: ShopContext, name: str, value: str, effective_from: str | None, set_by: str | None
) -> None:
    """Set a value from a day, leaving what came before it alone."""
    day = resolve_day(effective_from, shop)
    with shop.open_for_write() as handle:
        written = SettingRepository(handle.connection).set(name, value, day, set_by)
    click.echo(str(written))


@setting.command("list")
@click.option("--on", "day", default=None, help="the day to read them for")
@pass_shop
def list_settings(shop: ShopContext, day: str | None) -> None:
    """What the shop is working to."""
    when = resolve_day(day, shop)
    with shop.open() as handle:
        current = SettingRepository(handle.connection).settings().current(when)
    click.echo(
        render_table(
            ["setting", "value", "default"],
            [[name, current[name], DEFAULTS[name]] for name in known_settings()],
            right=(1, 2),
        )
    )


@setting.command("history")
@click.argument("name")
@pass_shop
def history(shop: ShopContext, name: str) -> None:
    """Every value a setting has had."""
    with shop.open() as handle:
        found = SettingRepository(handle.connection).history(name)
    if not found:
        click.echo(f"{name} has never been set; it runs on {DEFAULTS.get(name, 'nothing')}")
        return
    for item in found:
        click.echo(str(item))
