"""Reading and writing negotiated prices."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from fractions import Fraction

from starstamp.errors import ConflictError
from starstamp.model.contract import Contract, ContractTerm
from starstamp.model.money import Money
from starstamp.model.pricing import normalise_charge_code
from starstamp.store.repository import (
    Repository,
    as_day,
    as_optional_day,
    as_optional_int,
    as_text,
    day_text,
    optional_day_text,
)


def row_to_term(row: sqlite3.Row, owner_code: str) -> ContractTerm:
    cents = as_optional_int(row["cents"])
    numerator = as_optional_int(row["discount_numerator"])
    denominator = as_optional_int(row["discount_denominator"])
    return ContractTerm(
        owner_code=owner_code,
        code=as_text(row["code"]),
        effective_from=as_day(row["effective_from"]),
        amount=None if cents is None else Money(cents),
        discount_percent=(
            None if numerator is None or denominator is None else Fraction(numerator, denominator)
        ),
        effective_until=as_optional_day(row["effective_until"]),
    )


class ContractRepository(Repository):
    _SELECT = (
        "SELECT t.*, o.code AS owner_code FROM contract_term t"
        " JOIN owner_account o ON o.id = t.owner_id"
    )

    def add(self, term: ContractTerm, owner_id: int) -> int:
        discount = term.discount_percent
        try:
            cursor = self.connection.execute(
                "INSERT INTO contract_term (owner_id, code, cents, discount_numerator,"
                " discount_denominator, effective_from, effective_until)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    owner_id,
                    term.code,
                    None if term.amount is None else term.amount.cents,
                    None if discount is None else discount.numerator,
                    None if discount is None else discount.denominator,
                    day_text(term.effective_from),
                    optional_day_text(term.effective_until),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(
                f"{term.owner_code} already has a {term.code} term starting {term.effective_from}"
            ) from exc
        return int(cursor.lastrowid or 0)

    def agree(self, term: ContractTerm, owner_id: int) -> ContractTerm:
        """Close whatever term is open for that code and open this one."""
        self.connection.execute(
            "UPDATE contract_term SET effective_until = ?"
            " WHERE owner_id = ? AND code = ? AND effective_until IS NULL"
            " AND effective_from < ?",
            (
                day_text(term.effective_from - timedelta(days=1)),
                owner_id,
                term.code,
                day_text(term.effective_from),
            ),
        )
        self.add(term, owner_id)
        return term

    def contract(self, owner_code: str) -> Contract:
        rows = self._all(
            f"{self._SELECT} WHERE o.code = ? ORDER BY t.code, t.effective_from",
            (owner_code.upper(),),
        )
        return Contract(
            owner_code.upper(),
            tuple(row_to_term(row, owner_code.upper()) for row in rows),
        )

    def for_code(self, owner_code: str, code: str) -> list[ContractTerm]:
        rows = self._all(
            f"{self._SELECT} WHERE o.code = ? AND t.code = ? ORDER BY t.effective_from",
            (owner_code.upper(), normalise_charge_code(code)),
        )
        return [row_to_term(row, owner_code.upper()) for row in rows]

    def current(self, owner_code: str, day: date) -> list[ContractTerm]:
        return [term for term in self.contract(owner_code).terms if term.applies_on(day)]

    def accounts_with_terms(self) -> list[str]:
        rows = self._all(
            "SELECT DISTINCT o.code AS code FROM contract_term t"
            " JOIN owner_account o ON o.id = t.owner_id ORDER BY o.code"
        )
        return [as_text(row["code"]) for row in rows]
