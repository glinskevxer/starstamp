import pytest

from .conftest import DAY, Invoke


@pytest.fixture
def counter(running_shop: Invoke) -> Invoke:
    running_shop(
        "cylinder",
        "register",
        "PST/B12",
        "--owner",
        "WELD1",
        "--spec",
        "DOT-3AA2015",
        "--dom",
        "04-01",
        "--service",
        "AR",
        "--ree",
        "125.0",
        "--wall",
        "0.220",
    )
    running_shop(
        "lot",
        "receive",
        "weld1",
        "NCI/A4471",
        "PST/B12",
        "--on",
        "2024-06-03",
        "--promised",
        "2024-06-28",
        "--carrier",
        "Mountain Freight",
    )
    return running_shop


def requalify(shop: Invoke, key: str) -> None:
    shop(
        "requal",
        "run",
        key,
        "--tech",
        "jt7",
        "--system",
        "WJ-1",
        "--on",
        DAY,
        "--applied",
        "3358",
        "--total",
        "110.0",
        "--permanent",
        "2.0",
    )


def test_receiving_a_lot(counter: Invoke) -> None:
    out = counter("--today", "2024-06-15", "lot", "show", "L2024-0001").output
    assert "Mountain Freight" in out
    assert "NCI/A4471" in out
    assert "12 days" in out


def test_the_open_list_flags_a_late_lot(counter: Invoke) -> None:
    out = counter("--today", "2024-07-03", "lot", "open").output
    assert "L2024-0001" in out
    assert "late:" in out
    assert "5 days past the promise" in out


def test_nothing_in_the_shop(running_shop: Invoke) -> None:
    assert "nothing in the shop" in running_shop("lot", "open").output


def test_a_lot_is_not_ready_until_everything_is_decided(counter: Invoke) -> None:
    requalify(counter, "NCI/A4471")
    counter("lot", "ready", "L2024-0001", expect=4)
    requalify(counter, "PST/B12")
    assert "is ready, 2 cylinders settled" in counter("lot", "ready", "L2024-0001").output


def test_a_lot_goes_back(counter: Invoke) -> None:
    requalify(counter, "NCI/A4471")
    requalify(counter, "PST/B12")
    counter("lot", "ready", "L2024-0001")
    out = counter("lot", "return", "L2024-0001", "--on", "2024-06-20").output
    assert "went back on 2024-06-20 after 17 days" in out
    assert "in_service" in counter("cylinder", "show", "NCI/A4471").output


def test_adding_to_an_open_lot(counter: Invoke) -> None:
    counter(
        "cylinder",
        "register",
        "PST/B13",
        "--owner",
        "WELD1",
        "--spec",
        "DOT-3AA2015",
        "--dom",
        "04-01",
        "--service",
        "AR",
    )
    assert "1 added to L2024-0001" in counter("lot", "add", "L2024-0001", "PST/B13").output


def test_the_history_for_an_account(counter: Invoke) -> None:
    requalify(counter, "NCI/A4471")
    requalify(counter, "PST/B12")
    counter("lot", "ready", "L2024-0001")
    counter("lot", "return", "L2024-0001", "--on", "2024-06-20")
    out = counter("--today", "2024-07-01", "lot", "history", "weld1").output
    assert "returned" in out
    assert "1 returned, 17.0 days on average" in out


def test_no_lots_for_an_account(running_shop: Invoke) -> None:
    assert "no lots for WELD1" in running_shop("lot", "history", "weld1").output
