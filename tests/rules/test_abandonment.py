from datetime import date

from starstamp.model.lot import Lot, LotStatus
from starstamp.rules.abandonment import (
    NOTICE_WAIT_DAYS,
    READY_MONTHS,
    Abandonment,
    Standing,
    standing_for,
)

RECEIVED = date(2023, 1, 10)


def a_lot(**changes: object) -> Lot:
    base: dict[str, object] = {
        "number": "L2023-0007",
        "owner_code": "WELD1",
        "received_on": RECEIVED,
        "status": LotStatus.READY,
    }
    base.update(changes)
    return Lot(**base)  # type: ignore[arg-type]


def test_a_lot_still_being_worked_on_is_not_abandoned() -> None:
    standing = standing_for(a_lot(status=LotStatus.RECEIVED), date(2030, 1, 1))
    assert standing.standing is Standing.IN_HAND
    assert standing.days_ready == 0
    assert standing.next_step_on() is None


def test_a_lot_ready_a_month_ago_is_in_hand() -> None:
    standing = standing_for(a_lot(), date(2023, 2, 10))
    assert standing.standing is Standing.IN_HAND
    assert "has been ready 31 days" in standing.describe()
    assert standing.next_step_on() == date(2023, 7, 9)


def test_a_lot_ready_six_months_ago_needs_a_letter() -> None:
    standing = standing_for(a_lot(), date(2023, 8, 1))
    assert standing.standing is Standing.OVERDUE
    assert standing.standing.needs_a_letter
    assert "nobody has written to WELD1" in standing.describe()


def test_a_letter_starts_the_second_clock() -> None:
    standing = standing_for(a_lot(), date(2023, 8, 1), written_on=date(2023, 8, 1))
    assert standing.standing is Standing.WRITTEN_TO
    assert not standing.standing.may_be_disposed_of
    assert standing.next_step_on() == date(2023, 9, 30)


def test_the_lot_is_abandoned_once_both_clocks_have_run() -> None:
    standing = standing_for(a_lot(), date(2023, 10, 15), written_on=date(2023, 8, 1))
    assert standing.standing is Standing.ABANDONED
    assert standing.standing.may_be_disposed_of
    assert standing.days_since_letter == 75
    assert "did not come" in standing.describe()


def test_the_promise_date_starts_the_clock_when_there_is_one() -> None:
    standing = standing_for(a_lot(promised_on=date(2023, 3, 1)), date(2023, 8, 1))
    assert standing.days_ready == 153
    assert standing.standing is Standing.IN_HAND


def test_the_two_periods_are_named() -> None:
    assert READY_MONTHS == 6
    assert NOTICE_WAIT_DAYS == 60


def test_a_standing_with_no_ready_date() -> None:
    standing = Abandonment("L1", "WELD1", None, None, date(2024, 1, 1))
    assert standing.standing is Standing.IN_HAND
    assert standing.days_since_letter == 0
