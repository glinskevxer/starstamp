from datetime import date

from starstamp.model.lot import Lot, LotStatus
from starstamp.model.money import Money
from starstamp.rules.storage import chargeable, days_for

RECEIVED = date(2024, 6, 3)
FREE = 30


def a_lot(number: str = "L2024-0007", **changes: object) -> Lot:
    base: dict[str, object] = {
        "number": number,
        "owner_code": "WELD1",
        "received_on": RECEIVED,
    }
    base.update(changes)
    return Lot(**base)  # type: ignore[arg-type]


def test_a_lot_inside_the_free_period() -> None:
    days = days_for(a_lot(), date(2024, 6, 20), FREE)
    assert days.days_held == 17
    assert days.chargeable_days == 0
    assert not days.is_chargeable
    assert "inside the 30 free" in days.describe()


def test_the_clock_starts_after_the_free_days() -> None:
    days = days_for(a_lot(), date(2024, 7, 10), FREE)
    assert days.days_held == 37
    assert days.chargeable_days == 7
    assert "7 of them chargeable" in days.describe()


def test_a_returned_lot_stops_the_clock() -> None:
    returned = a_lot(status=LotStatus.RETURNED, returned_on=date(2024, 7, 10))
    days = days_for(returned, date(2024, 12, 1), FREE)
    assert days.chargeable_days == 7


def test_the_charge_is_the_rate_by_the_days() -> None:
    days = days_for(a_lot(), date(2024, 7, 10), FREE)
    assert days.charge(Money.parse("0.25")) == Money.parse("1.75")
    assert days_for(a_lot(), date(2024, 6, 20), FREE).charge(Money.parse("0.25")).cents == 0


def test_a_shorter_free_period_charges_sooner() -> None:
    assert days_for(a_lot(), date(2024, 6, 20), 7).chargeable_days == 10


def test_a_lot_received_today() -> None:
    assert days_for(a_lot(), RECEIVED, FREE).days_held == 0


def test_the_longest_stay_comes_first() -> None:
    lots = [
        a_lot("L2024-0001"),
        a_lot("L2024-0002", received_on=date(2024, 5, 1)),
        a_lot("L2024-0003", received_on=date(2024, 7, 1)),
    ]
    found = chargeable(lots, date(2024, 7, 20), FREE)
    assert [item.lot_number for item in found] == ["L2024-0002", "L2024-0001"]
    assert found[0].chargeable_days == 50


def test_nothing_chargeable() -> None:
    assert chargeable([a_lot()], date(2024, 6, 10), FREE) == []
