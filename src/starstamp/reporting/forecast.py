"""What is coming, from what is already in the book.

Every cylinder that passed carries its own due date, so the shop's next two
years of work is not a guess: it is a count of due dates, and the money beside
it is that count at the prices those accounts have agreed. What it cannot know
is whether the cylinders will actually turn up, which is why the counts are
reported per account rather than as one number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.cylinder import CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.money import Money, total
from starstamp.model.pricing import code_for
from starstamp.service.fill import FillService
from starstamp.store.contracts import ContractRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.pricing import PriceRepository
from starstamp.text.table import render_table


@dataclass(frozen=True)
class MonthAhead:
    """One month, what falls due in it and what that is worth."""

    month: StampedMonth
    cylinders: int
    value: Money
    by_owner: dict[str, int]

    def row(self) -> list[str]:
        return [self.month.long_form(), str(self.cylinders), str(self.value)]


@dataclass(frozen=True)
class Forecast:
    """The months ahead, and anything already overdue."""

    from_day: date
    months: tuple[MonthAhead, ...]
    overdue: int

    @property
    def cylinders(self) -> int:
        return sum(month.cylinders for month in self.months)

    @property
    def value(self) -> Money:
        return total([month.value for month in self.months])

    def busiest(self) -> MonthAhead | None:
        if not self.months:
            return None
        return max(self.months, key=lambda month: (month.cylinders, month.month.long_form()))

    def describe(self) -> str:
        if not self.months:
            head = f"nothing falls due after {self.from_day.isoformat()}"
            if self.overdue:
                return f"{head}; {self.overdue} already out of test"
            return head
        busiest = self.busiest()
        line = (
            f"{self.cylinders} cylinders due over {len(self.months)} months, "
            f"worth {self.value.with_symbol()}"
        )
        if busiest is not None:
            line = f"{line}; busiest is {busiest.month.long_form()} with {busiest.cylinders}"
        if self.overdue:
            line = f"{line}; {self.overdue} already out of test"
        return line


def build(book: Book, from_day: date, months: int) -> Forecast:
    cylinders = CylinderRepository(book.connection)
    prices = PriceRepository(book.connection).book()
    contracts = ContractRepository(book.connection)
    fill = FillService(book)

    fleet = [
        cylinder
        for status in (CylinderStatus.IN_SERVICE, CylinderStatus.IN_SHOP)
        for cylinder in cylinders.with_status(status)
    ]
    horizon = StampedMonth.of(from_day).plus_months(max(months, 0))
    buckets: dict[str, list[tuple[str, Money]]] = {}
    overdue = 0

    for cylinder in fleet:
        row = fill.due_row(cylinder, from_day)
        if row.due is None or row.last_pass is None:
            continue
        if row.overdue:
            overdue += 1
            continue
        if row.due > horizon:
            continue
        code = code_for(row.last_pass.method)
        try:
            list_price = prices.amount(code, from_day)
        except Exception:  # noqa: BLE001 - an unpriced code forecasts at nothing
            list_price = Money.zero()
        agreed = contracts.contract(cylinder.owner_code).price(code, from_day, list_price)
        buckets.setdefault(row.due.long_form(), []).append((cylinder.owner_code, agreed))

    ahead: list[MonthAhead] = []
    for label in sorted(buckets):
        rows = buckets[label]
        owners: dict[str, int] = {}
        for owner_code, _ in rows:
            owners[owner_code] = owners.get(owner_code, 0) + 1
        year, _, month = label.partition("-")
        ahead.append(
            MonthAhead(
                month=StampedMonth(int(year), int(month)),
                cylinders=len(rows),
                value=total([amount for _, amount in rows]),
                by_owner=dict(sorted(owners.items())),
            )
        )
    return Forecast(from_day, tuple(ahead), overdue)


def render(forecast: Forecast) -> str:
    lines = [forecast.describe()]
    if not forecast.months:
        return lines[0]
    lines.append("")
    lines.append(
        render_table(
            ["month", "cylinders", "value"],
            [month.row() for month in forecast.months],
            right=(1, 2),
        )
    )
    busiest = forecast.busiest()
    if busiest is not None and busiest.by_owner:
        lines.append("")
        lines.append(f"{busiest.month.long_form()} by account:")
        for owner_code, count in busiest.by_owner.items():
            lines.append(f"  {owner_code} {count}")
    return "\n".join(lines)
