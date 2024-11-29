import pytest

from .conftest import Invoke
from .test_endtoend import DAY, running_shop  # noqa: F401


@pytest.fixture
def tested(running_shop: Invoke) -> Invoke:  # noqa: F811
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
    return running_shop


def test_the_packet_prints(tested: Invoke) -> None:
    out = tested("--today", "2026-01-04", "report", "packet", "NCI/A4471").output
    assert "DOT-3AA2015" in out
    assert "calibrated_cylinder CC-88012" in out
    assert "packet drawn 2026-01-04" in out


def test_a_packet_for_a_cylinder_with_no_tests(running_shop: Invoke) -> None:  # noqa: F811
    assert "no records of test" in running_shop("report", "packet", "NCI/A4471").output


def test_throughput_by_month(tested: Invoke) -> None:
    out = tested("report", "throughput", "--from", "2024-06-01", "--to", "2024-06-30").output
    assert "2024-06" in out
    assert "1 records, 1 passed" in out


def test_throughput_by_method_and_technician(tested: Invoke) -> None:
    by_method = tested(
        "report", "throughput", "--from", "2024-01-01", "--to", "2024-12-31", "--by", "method"
    ).output
    assert "volumetric" in by_method
    by_tech = tested(
        "report", "throughput", "--from", "2024-01-01", "--to", "2024-12-31", "--by", "technician"
    ).output
    assert "JT7" in by_tech


def test_throughput_defaults_to_this_month(tested: Invoke) -> None:
    out = tested("--today", "2024-06-30", "report", "throughput").output
    assert "2024-06-01 to 2024-06-30" in out


def test_the_day_report(tested: Invoke) -> None:
    out = tested("report", "day", "--on", DAY).output
    assert "NCI/A4471 volumetric pass" in out
    assert "nothing on 2024-06-13" in tested("report", "day", "--on", "2024-06-13").output


def test_the_rig_report(tested: Invoke) -> None:
    out = tested("report", "rig", "--from", "2024-06-01", "--to", "2024-06-30").output
    assert "WJ-1" in out
    assert "drift" in out


def test_the_rig_report_for_one_system(tested: Invoke) -> None:
    out = tested("report", "rig", "wj-1", "--from", "2024-06-01", "--to", "2024-06-30").output
    assert "1 tested" in out


def test_the_rig_report_with_nothing_on_file(shop: Invoke) -> None:
    assert "no test systems on file" in shop("report", "rig").output


def test_the_fleet_report(tested: Invoke) -> None:
    out = tested("report", "fleet", "weld1", "--on", "2034-04-01").output
    assert "WELD1 holds 1 cylinders" in out
    assert "due month" in out


def test_the_floor_report(tested: Invoke) -> None:
    assert "nothing of WELD1 is in the shop" in tested("report", "floor", "weld1").output
    tested(
        "requal",
        "run",
        "NCI/A4471",
        "--tech",
        "jt7",
        "--system",
        "WJ-1",
        "--on",
        "2024-06-13",
        "--applied",
        "3358",
        "--total",
        "110.0",
        "--permanent",
        "2.0",
        "--defect",
        "threads",
        expect=5,
    )


def test_the_condemnation_report(running_shop: Invoke) -> None:  # noqa: F811
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
    out = running_shop(
        "report", "condemnations", "--from", "2024-01-01", "--to", "2024-12-31"
    ).output
    assert "1 condemned between" in out
    assert "bulge" in out
    assert "1990s" in out


def test_a_quiet_condemnation_report(tested: Invoke) -> None:
    out = tested("report", "condemnations", "--from", "2023-01-01", "--to", "2023-12-31").output
    assert "nothing condemned" in out


def test_the_bench_sheet(running_shop: Invoke) -> None:  # noqa: F811
    assert "nothing on the bench" in running_shop("report", "bench").output
    running_shop(
        "lot", "receive", "weld1", "NCI/A4471", "--on", "2024-06-03", "--promised", "2024-06-28"
    )
    out = running_shop("--today", "2024-06-12", "report", "bench").output
    assert "L2024-0001" in out
    assert "NCI/A4471" in out
    assert "in_shop" in out


def test_the_bench_sheet_shows_what_a_cylinder_is_held_for(running_shop: Invoke) -> None:  # noqa: F811
    running_shop("lot", "receive", "weld1", "NCI/A4471", "--on", "2024-06-03")
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
        "threads",
    )
    out = running_shop("report", "bench").output
    assert "nothing on the bench" in out
