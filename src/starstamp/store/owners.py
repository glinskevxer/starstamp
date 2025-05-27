"""Reading and writing customer accounts."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import date

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.owner import OwnerAccount, normalise_owner_code
from starstamp.store.repository import (
    Repository,
    as_int,
    as_optional_day,
    as_optional_text,
    as_text,
    day_text,
    optional_day_text,
)


def row_to_owner(row: sqlite3.Row) -> OwnerAccount:
    opened = as_optional_day(row["opened_on"])
    if opened is None:
        raise ValueError("an account row without an opening date is corrupt")
    return OwnerAccount(
        code=as_text(row["code"]),
        name=as_text(row["name"]),
        opened_on=opened,
        contact=as_optional_text(row["contact"]),
        terms_days=as_int(row["terms_days"]),
        closed_on=as_optional_day(row["closed_on"]),
        address=as_optional_text(row["address"]),
        phone=as_optional_text(row["phone"]),
        email=as_optional_text(row["email"]),
        note=as_optional_text(row["note"]),
    )


class OwnerRepository(Repository):
    def add(self, account: OwnerAccount) -> int:
        try:
            cursor = self.connection.execute(
                "INSERT INTO owner_account (code, name, contact, terms_days, opened_on,"
                " closed_on, address, phone, email, note)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    account.code,
                    account.name,
                    account.contact,
                    account.terms_days,
                    day_text(account.opened_on),
                    optional_day_text(account.closed_on),
                    account.address,
                    account.phone,
                    account.email,
                    account.note,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"account {account.code} is already on the books") from exc
        return int(cursor.lastrowid or 0)

    def by_code(self, code: str) -> OwnerAccount:
        wanted = normalise_owner_code(code)
        row = self._one(
            "SELECT * FROM owner_account WHERE code = ?",
            (wanted,),
            f"no account {wanted}",
        )
        return row_to_owner(row)

    def id_of(self, code: str) -> int:
        wanted = normalise_owner_code(code)
        row = self._one(
            "SELECT id FROM owner_account WHERE code = ?",
            (wanted,),
            f"no account {wanted}",
        )
        return as_int(row["id"])

    def code_of(self, owner_id: int) -> str:
        row = self._one(
            "SELECT code FROM owner_account WHERE id = ?",
            (owner_id,),
            f"no account with id {owner_id}",
        )
        return as_text(row["code"])

    def all(self) -> list[OwnerAccount]:
        return [row_to_owner(row) for row in self._all("SELECT * FROM owner_account ORDER BY code")]

    def open_on(self, day: date) -> list[OwnerAccount]:
        return [account for account in self.all() if account.open_on(day)]

    def update_details(
        self,
        code: str,
        *,
        contact: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        note: str | None = None,
    ) -> OwnerAccount:
        """Change how the shop reaches an account, leaving the rest alone."""
        account = self.by_code(code)
        updated = replace(
            account,
            contact=contact if contact is not None else account.contact,
            address=address if address is not None else account.address,
            phone=phone if phone is not None else account.phone,
            email=email if email is not None else account.email,
            note=note if note is not None else account.note,
        )
        self.connection.execute(
            "UPDATE owner_account SET contact = ?, address = ?, phone = ?, email = ?,"
            " note = ? WHERE code = ?",
            (
                updated.contact,
                updated.address,
                updated.phone,
                updated.email,
                updated.note,
                account.code,
            ),
        )
        return self.by_code(code)

    def without_an_address(self) -> list[OwnerAccount]:
        """Open accounts the shop could not write to if it had to."""
        return [
            account for account in self.all() if account.is_open and not account.can_be_written_to
        ]

    def close(self, code: str, day: date) -> OwnerAccount:
        account = self.by_code(code)
        if not account.is_open:
            raise ConflictError(f"account {account.code} closed on {account.closed_on}")
        if day < account.opened_on:
            raise ConflictError(f"account {account.code} opened on {account.opened_on}")
        self.connection.execute(
            "UPDATE owner_account SET closed_on = ? WHERE code = ?",
            (day_text(day), account.code),
        )
        return self.by_code(code)

    def reopen(self, code: str) -> OwnerAccount:
        account = self.by_code(code)
        if account.is_open:
            raise ConflictError(f"account {account.code} is already open")
        self.connection.execute(
            "UPDATE owner_account SET closed_on = NULL WHERE code = ?", (account.code,)
        )
        return self.by_code(code)

    def require_open(self, code: str, day: date) -> OwnerAccount:
        account = self.by_code(code)
        if not account.open_on(day):
            raise NotFoundError(f"account {account.code} was not open on {day.isoformat()}")
        return account
