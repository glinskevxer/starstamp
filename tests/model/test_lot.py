from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.lot import Lot, LotLine, LotStatus, format_lot_number, parse_lot_number

RECEIVED = date(2024, 6, 3)


def a_lot(**changes: object) -> Lot:
    base: dict[str, object] = {
        "number": "L2024-0007",
        "owner_code": "WELD1",
        "received_on": RECEIVED,
        "promised_on": date(2024, 6, 28),
    }
    base.update(changes)
    return Lot(**base)  # type: ignore[arg-type]


def test_lot_numbers_format_and_parse() -> None:
    assert format_lot_number(2024, 7) == "L2024-0007"
    assert parse_lot_number("l2024-0007") == (2024, 7)


@pytest.mark.parametrize("text", ["2024-0007", "L24-7", "", "L2024-00071"])
def test_bad_lot_numbers(text: str) -> None:
    with pytest.raises(ValidationError, match="LYYYY-NNNN"):
        parse_lot_number(text)


def test_out_of_range_pieces() -> None:
    with pytest.raises(ValidationError, match="lot year"):
        format_lot_number(1200, 7)
    with pytest.raises(ValidationError, match="1 to 9999"):
        format_lot_number(2024, 0)


def test_a_lot_promised_before_it_arrived() -> None:
    with pytest.raises(ValidationError, match="promised before it arrived"):
        a_lot(promised_on=date(2024, 6, 1))


def test_a_lot_returned_before_it_arrived() -> None:
    with pytest.raises(ValidationError, match="cannot go back before"):
        a_lot(status=LotStatus.RETURNED, returned_on=date(2024, 5, 1))


def test_the_status_and_the_return_date_have_to_agree() -> None:
    with pytest.raises(ValidationError, match="does not agree"):
        a_lot(status=LotStatus.RETURNED)
    with pytest.raises(ValidationError, match="does not agree"):
        a_lot(returned_on=date(2024, 6, 20))


def test_days_in_shop_runs_to_today_while_it_is_here() -> None:
    assert a_lot().days_in_shop(date(2024, 6, 20)) == 17


def test_days_in_shop_stops_at_the_return() -> None:
    returned = a_lot(status=LotStatus.RETURNED, returned_on=date(2024, 6, 20))
    assert returned.days_in_shop(date(2024, 7, 30)) == 17


def test_late_only_counts_while_it_is_still_here() -> None:
    lot = a_lot()
    assert not lot.is_late(date(2024, 6, 28))
    assert lot.is_late(date(2024, 6, 29))
    assert lot.days_late(date(2024, 7, 3)) == 5
    returned = a_lot(status=LotStatus.RETURNED, returned_on=date(2024, 6, 20))
    assert not returned.is_late(date(2024, 7, 3))
    assert returned.days_late(date(2024, 7, 3)) == 0


def test_a_lot_with_no_promise_is_never_late() -> None:
    assert not a_lot(promised_on=None).is_late(date(2030, 1, 1))


def test_status_predicates() -> None:
    assert LotStatus.RECEIVED.accepts_work
    assert LotStatus.IN_PROGRESS.accepts_work
    assert not LotStatus.READY.accepts_work
    assert LotStatus.READY.is_open
    assert not LotStatus.RETURNED.is_open


def test_lines() -> None:
    line = LotLine(lot_number="L2024-0007", cylinder_key="NCI/A4471", added_on=RECEIVED)
    assert not line.is_settled
    assert str(line) == "NCI/A4471 on L2024-0007: open"
    settled = LotLine(
        lot_number="L2024-0007",
        cylinder_key="NCI/A4471",
        added_on=RECEIVED,
        disposition="requalified",
        event_id=4,
    )
    assert settled.is_settled
    assert "requalified" in str(settled)


def test_text_form() -> None:
    assert str(a_lot()) == "L2024-0007 for WELD1"
