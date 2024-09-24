"""Reading and writing notices to owners."""

from __future__ import annotations

import sqlite3
from datetime import date

from starstamp.errors import ConflictError
from starstamp.model.notice import Notice, NoticeKind, NoticeState
from starstamp.store.repository import (
    Repository,
    as_day,
    as_int,
    as_optional_day,
    as_optional_int,
    as_text,
    day_text,
)


def row_to_notice(row: sqlite3.Row) -> Notice:
    return Notice(
        owner_code=as_text(row["owner_code"]),
        cylinder_key=as_text(row["cylinder_key"]),
        kind=NoticeKind(as_text(row["kind"])),
        raised_on=as_day(row["raised_on"]),
        body=as_text(row["body"]),
        state=NoticeState(as_text(row["state"])),
        sent_on=as_optional_day(row["sent_on"]),
        event_id=as_optional_int(row["requalification_id"]),
        notice_id=as_int(row["id"]),
    )


class NoticeRepository(Repository):
    _SELECT = (
        "SELECT n.*, o.code AS owner_code,"
        " c.manufacturer_symbol || '/' || c.serial AS cylinder_key FROM notice n"
        " JOIN owner_account o ON o.id = n.owner_id"
        " JOIN cylinder c ON c.id = n.cylinder_id"
    )

    def add(self, notice: Notice, owner_id: int, cylinder_id: int) -> Notice:
        cursor = self.connection.execute(
            "INSERT INTO notice (owner_id, cylinder_id, kind, raised_on, body, state, sent_on,"
            " requalification_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner_id,
                cylinder_id,
                notice.kind.value,
                day_text(notice.raised_on),
                notice.body,
                notice.state.value,
                None if notice.sent_on is None else day_text(notice.sent_on),
                notice.event_id,
            ),
        )
        return self.by_id(int(cursor.lastrowid or 0))

    def by_id(self, notice_id: int) -> Notice:
        return row_to_notice(
            self._one(f"{self._SELECT} WHERE n.id = ?", (notice_id,), f"no notice {notice_id}")
        )

    def for_owner(self, owner_code: str) -> list[Notice]:
        rows = self._all(
            f"{self._SELECT} WHERE o.code = ? ORDER BY n.raised_on, n.id", (owner_code.upper(),)
        )
        return [row_to_notice(row) for row in rows]

    def unsent(self) -> list[Notice]:
        rows = self._all(
            f"{self._SELECT} WHERE n.state = ? ORDER BY n.raised_on, n.id",
            (NoticeState.DRAFTED.value,),
        )
        return [row_to_notice(row) for row in rows]

    def for_event(self, event_id: int) -> list[Notice]:
        rows = self._all(
            f"{self._SELECT} WHERE n.requalification_id = ? ORDER BY n.id", (event_id,)
        )
        return [row_to_notice(row) for row in rows]

    def send(self, notice_id: int, day: date) -> Notice:
        notice = self.by_id(notice_id)
        if notice.state.is_sent:
            raise ConflictError(f"notice {notice_id} went out on {notice.sent_on}")
        if day < notice.raised_on:
            raise ConflictError(f"notice {notice_id} was drafted on {notice.raised_on}")
        self.connection.execute(
            "UPDATE notice SET state = ?, sent_on = ? WHERE id = ?",
            (NoticeState.SENT.value, day_text(day), notice_id),
        )
        return self.by_id(notice_id)

    def count(self) -> int:
        return self._count("SELECT count(*) FROM notice")
