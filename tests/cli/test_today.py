from .conftest import DAY, Invoke


def test_a_quiet_morning(running_shop: Invoke) -> None:
    out = running_shop("today", "--on", DAY).output
    assert "Wednesday 12 June 2024" in out
    assert "0 of 24 booked" in out
    assert "rigs in calibration: WJ-1" in out
    assert "nothing on the bench" in out
    assert "nothing outstanding" in out


def test_a_morning_with_work_in(running_shop: Invoke) -> None:
    running_shop("lot", "receive", "weld1", "NCI/A4471", "--on", "2024-06-03")
    out = running_shop("today", "--on", DAY).output
    assert "L2024-0001" in out
    assert "NCI/A4471" in out


def test_a_booking_shows(running_shop: Invoke) -> None:
    running_shop("--today", "2024-06-03", "book", "in", "weld1", "6", "--for", DAY)
    out = running_shop("today", "--on", DAY).output
    assert "booked in: WELD1 6" in out
    assert "6 of 24 booked" in out


def test_the_urgent_things_come_first(running_shop: Invoke) -> None:
    running_shop(
        "requal",
        "run",
        "NCI/A4471",
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
        "--defect",
        "bulge",
    )
    running_shop("notice", "draft", "--on", "2024-06-13")
    out = running_shop("today", "--on", "2024-07-20").output
    assert "today: letter overdue" in out
    assert "things outstanding in all" in out


def test_a_day_with_things_outstanding_but_nothing_urgent(running_shop: Invoke) -> None:
    running_shop(
        "requal",
        "run",
        "NCI/A4471",
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
    out = running_shop("today", "--on", DAY).output
    assert "none of them urgent" in out


def test_the_quiet_flag_leaves_the_bench_out(running_shop: Invoke) -> None:
    running_shop("lot", "receive", "weld1", "NCI/A4471", "--on", "2024-06-03")
    out = running_shop("today", "--on", DAY, "--quiet").output
    assert "NCI/A4471" not in out
    assert "booked" in out
