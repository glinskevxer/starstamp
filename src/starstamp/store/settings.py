"""Reading and writing the shop's own numbers."""

from __future__ import annotations

import sqlite3
from datetime import date

from starstamp.errors import ConflictError
from starstamp.model.settings import Setting, Settings, check_value
from starstamp.store.repository import Repository, as_day, as_text, day_text


def row_to_setting(row: sqlite3.Row) -> Setting:
    return Setting(
        name=as_text(row["name"]),
        value=as_text(row["value"]),
        effective_from=as_day(row["effective_from"]),
    )


class SettingRepository(Repository):
    def set(self, name: str, value: str, day: date, set_by: str | None = None) -> Setting:
        checked = check_value(name, value)
        try:
            self.connection.execute(
                "INSERT INTO shop_setting (name, value, effective_from, set_by)"
                " VALUES (?, ?, ?, ?)",
                (name, checked, day_text(day), set_by),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"{name} was already set from {day.isoformat()}") from exc
        return Setting(name, checked, day)

    def settings(self) -> Settings:
        rows = self._all("SELECT * FROM shop_setting ORDER BY name, effective_from")
        return Settings(tuple(row_to_setting(row) for row in rows))

    def history(self, name: str) -> list[Setting]:
        rows = self._all(
            "SELECT * FROM shop_setting WHERE name = ? ORDER BY effective_from", (name,)
        )
        return [row_to_setting(row) for row in rows]

    def integer(self, name: str, day: date) -> int:
        return self.settings().integer(name, day)
