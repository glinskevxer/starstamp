"""Everything the shop owes somebody, on one list.

Eight things in this package can be outstanding at once and each of them has
its own command. Nobody runs eight commands every morning, so this runs them
and prints what came back, in the order that things actually bite: the ones
with a legal clock on them first, then the ones with a customer waiting, then
the money.

It decides nothing. Every line here is something another part of the package
already worked out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.cylinder import CylinderStatus
from starstamp.reporting import unbilled
from starstamp.service.abandoned import AbandonedService
from starstamp.service.disposal import DisposalService
from starstamp.service.fill import FillService
from starstamp.service.notices import NoticeService
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.facility import FacilityRepository, TechnicianRepository
from starstamp.store.invoices import InvoiceRepository

CERTIFICATE_WARNING_DAYS = 60
SIGN_OFF_WARNING_DAYS = 60


@dataclass(frozen=True)
class Item:
    """One thing outstanding, and how much of a hurry it is in."""

    urgency: int
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.detail}"


@dataclass(frozen=True)
class Worklist:
    """The morning list."""

    day: date
    items: tuple[Item, ...]

    @property
    def is_clear(self) -> bool:
        return not self.items

    def of_kind(self, kind: str) -> tuple[Item, ...]:
        return tuple(item for item in self.items if item.kind == kind)

    def kinds(self) -> list[str]:
        return sorted({item.kind for item in self.items})

    def describe(self) -> str:
        if self.is_clear:
            return f"nothing outstanding on {self.day.isoformat()}"
        lines = [f"{len(self.items)} things outstanding on {self.day.isoformat()}"]
        lines.extend(f"  {item}" for item in self.items)
        return "\n".join(lines)


class WorklistService:
    def __init__(self, book: Book) -> None:
        self.book = book

    def build(self, day: date, *, due_within: int = 3) -> Worklist:
        items: list[Item] = []
        items.extend(self._legal_clocks(day))
        items.extend(self._customers(day, due_within))
        items.extend(self._money(day))
        items.extend(self._paperwork(day))
        items.sort(key=lambda item: (item.urgency, item.kind, item.detail))
        return Worklist(day, tuple(items))

    def _legal_clocks(self, day: date) -> list[Item]:
        found: list[Item] = []
        for notice in NoticeService(self.book).overdue_letters(day):
            found.append(Item(0, "letter overdue", f"{notice.cylinder_key} to {notice.owner_code}"))
        for waiting in DisposalService(self.book).late(day):
            found.append(Item(0, "not rendered", waiting.describe()))
        return found

    def _customers(self, day: date, due_within: int) -> list[Item]:
        found: list[Item] = []
        cylinders = CylinderRepository(self.book.connection)
        for cylinder in cylinders.with_status(CylinderStatus.AWAITING_REPAIR):
            found.append(Item(1, "held for repair", str(cylinder.key)))
        for row in FillService(self.book).due_within(day, due_within):
            if row.never_tested:
                continue
            when = "overdue" if row.overdue else f"due {row.due}"
            found.append(Item(2, "coming due", f"{row.cylinder.key} {when}"))
        for standing in AbandonedService(self.book).needing_a_letter(day):
            found.append(Item(1, "uncollected", standing.describe()))
        return found

    def _money(self, day: date) -> list[Item]:
        found: list[Item] = []
        outstanding = unbilled.build(self.book, day)
        if outstanding.events:
            found.append(
                Item(
                    3,
                    "unbilled",
                    f"{len(outstanding.events)} records worth {outstanding.value.with_symbol()}",
                )
            )
        for invoice in InvoiceRepository(self.book.connection).overdue(day):
            found.append(
                Item(
                    3,
                    "invoice overdue",
                    f"{invoice.number} {invoice.owner_code} "
                    f"{invoice.total.with_symbol()}, {invoice.days_overdue(day)} days",
                )
            )
        return found

    def _paperwork(self, day: date) -> list[Item]:
        found: list[Item] = []
        calibration = CalibrationRepository(self.book.connection)
        for system in calibration.systems():
            for certificate in calibration.certificates(system):
                left = certificate.days_left(day)
                if left < 0:
                    found.append(
                        Item(
                            1,
                            "certificate expired",
                            f"{system} {certificate.instrument} on "
                            f"{certificate.valid_until.isoformat()}",
                        )
                    )
                elif left <= CERTIFICATE_WARNING_DAYS:
                    found.append(
                        Item(
                            2,
                            "certificate due",
                            f"{system} {certificate.instrument} in {left} days",
                        )
                    )
        technicians = TechnicianRepository(self.book.connection)
        for person in technicians.lapsed_on(day):
            found.append(Item(1, "sign off lapsed", str(person)))
        for person in technicians.lapsing_within(day, SIGN_OFF_WARNING_DAYS):
            found.append(Item(2, "sign off due", str(person)))
        facilities = FacilityRepository(self.book.connection)
        for facility in facilities.all():
            left = (facility.approved_until - day).days
            if left < 0:
                found.append(Item(0, "rin lapsed", f"{facility.rin} on {facility.approved_until}"))
            elif left <= CERTIFICATE_WARNING_DAYS:
                found.append(Item(1, "rin due", f"{facility.rin} in {left} days"))
        return found
