from .conftest import Invoke


def test_booking_and_reading_the_day(running_shop: Invoke) -> None:
    out = running_shop(
        "--today", "2024-06-03", "book", "in", "weld1", "10", "--for", "2024-06-12"
    ).output
    assert "booked 2024-06-12 WELD1 10 cylinders" in out
    day = running_shop("book", "day", "--on", "2024-06-12").output
    assert "10 of 24 booked, 14 free" in day
    assert "WJ-1" in day


def test_a_day_with_nothing_on_it(running_shop: Invoke) -> None:
    assert "nothing promised" in running_shop("book", "day", "--on", "2024-06-13").output


def test_a_booking_past_capacity(running_shop: Invoke) -> None:
    running_shop("--today", "2024-06-03", "book", "in", "weld1", "20", "--for", "2024-06-12")
    result = running_shop(
        "--today", "2024-06-03", "book", "in", "weld1", "10", "--for", "2024-06-12", expect=5
    )
    assert "room for 4 more" in result.output


def test_the_week(running_shop: Invoke) -> None:
    running_shop("--today", "2024-06-03", "book", "in", "weld1", "24", "--for", "2024-06-12")
    out = running_shop("book", "week", "--from", "2024-06-12").output
    assert "2024-06-12" in out
    assert "2024-06-18" in out


def test_offers(running_shop: Invoke) -> None:
    running_shop("--today", "2024-06-03", "book", "in", "weld1", "24", "--for", "2024-06-12")
    out = running_shop("book", "offer", "10", "--from", "2024-06-12", "--within", "3").output
    assert "2024-06-13" in out
    assert "2024-06-12" not in out


def test_no_day_can_take_it(running_shop: Invoke) -> None:
    out = running_shop("book", "offer", "500", "--from", "2024-06-12", "--within", "3").output
    assert "no day in the next 3 could take 500" in out


def test_arriving_and_cancelling(running_shop: Invoke) -> None:
    running_shop("--today", "2024-06-03", "book", "in", "weld1", "2", "--for", "2024-06-12")
    running_shop("lot", "receive", "weld1", "NCI/A4471", "--on", "2024-06-12")
    out = running_shop("book", "arrive", "1", "L2024-0001").output
    assert "as L2024-0001" in out
    running_shop("--today", "2024-06-03", "book", "in", "weld1", "2", "--for", "2024-06-13")
    assert "cancelled" in running_shop("book", "cancel", "2", "--note", "put off").output


def test_missed_bookings(running_shop: Invoke) -> None:
    assert "nothing missed" in running_shop("book", "missed").output
    running_shop("--today", "2024-06-03", "book", "in", "weld1", "2", "--for", "2024-06-12")
    out = running_shop("book", "missed", "--on", "2024-06-20").output
    assert "8 days ago" in out
