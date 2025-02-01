"""Looking after the file: backups, restores and a health check."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from starstamp.cli.context import ShopContext, pass_shop
from starstamp.store import maintenance
from starstamp.text.table import render_pairs


@click.command("backup")
@click.argument("target", required=False, type=click.Path(dir_okay=False, path_type=Path))
@click.option("--overwrite", is_flag=True, help="replace a backup that is already there")
@pass_shop
def backup(shop: ShopContext, target: Path | None, overwrite: bool) -> None:
    """Copy the book safely, while it is in use."""
    where = target or maintenance.timestamped_name(shop.book_path, datetime.now())
    with shop.open() as handle:
        result = maintenance.backup(handle, where, overwrite=overwrite)
    click.echo(result.describe())


@click.command("restore")
@click.argument("source", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--overwrite", is_flag=True, help="replace the book that is there")
@pass_shop
def restore(shop: ShopContext, source: Path, overwrite: bool) -> None:
    """Put a backup back in place of the book."""
    result = maintenance.restore(source, shop.book_path, overwrite=overwrite)
    click.echo(f"restored {source} to {result.path}")


@click.command("verify")
@pass_shop
def verify(shop: ShopContext) -> None:
    """Ask the file whether it is sound."""
    with shop.open() as handle:
        result = maintenance.verify(handle)
    click.echo(
        render_pairs(
            [
                ("integrity", result.integrity),
                ("schema", f"{result.schema} of {result.expected_schema}"),
                ("broken references", str(result.foreign_keys_broken)),
                ("free pages", str(result.freelist_pages)),
            ]
        )
    )
    if not result.is_sound:
        raise SystemExit(9)


@click.command("vacuum")
@pass_shop
def vacuum(shop: ShopContext) -> None:
    """Rebuild the file and give back the space deletes left behind."""
    with shop.open() as handle:
        freed = maintenance.vacuum(handle)
    click.echo(f"{freed} bytes given back")
