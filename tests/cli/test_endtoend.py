"""A whole day in the shop, driven the way the bench drives it.

Every other suite tests a layer. This one types the commands in the order a
requalifier types them, because the seams between the commands are the part
nothing else covers: a rig certified under one code and tested under another,
a date given to one command and defaulted in the next.
"""

from __future__ import annotations

import pytest

from .conftest import Invoke

DAY = "2024-06-12"


@pytest.fixture
def running_shop(shop: Invoke) -> Invoke:
    shop(
        "account",
        "add",
        "weld1",
        "Cascade Welding Supply",
        "--contact",
        "Ruth Alvarez",
        "--opened",
        "2019-04-01",
    )
    shop(
        "facility",
        "add",
        "a419",
        "Wasatch Cylinder Service",
        "--from",
        "2021-05-01",
        "--until",
        "2026-04-30",
        "--methods",
        "volumetric,direct-expansion,proof,visual",
    )
    shop(
        "tech",
        "add",
        "jt7",
        "Jesse Tovar",
        "--methods",
        "volumetric,visual",
        "--from",
        "2022-03-01",
    )
    for instrument, serial in (
        ("calibrated cylinder", "CC-88012"),
        ("gauge", "PG-4471"),
        ("burette", "EB-19"),
    ):
        shop(
            "rig",
            "certify",
            "WJ-1",
            instrument,
            "--serial",
            serial,
            "--issued",
            "2024-01-15",
            "--until",
            "2029-01-15",
            "--by",
            "Rocky Mountain Calibration",
        )
    shop("rig", "check", "WJ-1", "40.0", "40.1", "--on", DAY, "--tech", "jt7")
    shop(
        "cylinder",
        "register",
        "NCI/A4471",
        "--owner",
        "WELD1",
        "--spec",
        "DOT-3AA2015",
        "--dom",
        "06-98",
        "--service",
        "N2",
        "--ree",
        "125.0",
        "--wall",
        "0.220",
        "--on",
        "2024-06-11",
    )
    return shop


def test_a_cylinder_goes_through_and_earns_its_star(running_shop: Invoke) -> None:
    out = running_shop(
        "requal",
        "run",
        "NCI/A4471",
        "--tech",
        "jt7",
        "--method",
        "volumetric",
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
    ).output
    assert "pass" in out
    assert "due 06-34" in out
    assert "starred" in out


def test_the_record_of_test_reads_back(running_shop: Invoke) -> None:
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
    history = running_shop("requal", "history", "NCI/A4471").output
    assert "volumetric" in history
    assert "A419" in history
    detail = running_shop("requal", "show", "1").output
    assert "3358 psig, held 30s" in detail
    assert "total 110.0 cc" in detail


def test_a_pit_too_deep_condemns_the_cylinder_before_the_rig(running_shop: Invoke) -> None:
    out = running_shop(
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
        "pitting:0.050",
    ).output
    assert "condemn" in out
    assert "isolated pitting" in out
    assert "condemned" in running_shop("cylinder", "show", "NCI/A4471").output


def test_a_rig_with_no_check_that_day_refuses_the_work(running_shop: Invoke) -> None:
    result = running_shop(
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
        expect=5,
    )
    assert "no start of day check" in result.output


def test_a_technician_without_the_sign_off_is_turned_away(running_shop: Invoke) -> None:
    running_shop(
        "tech",
        "add",
        "mr2",
        "Marisol Reyes",
        "--methods",
        "visual",
        "--from",
        "2023-01-09",
    )
    result = running_shop(
        "requal",
        "run",
        "NCI/A4471",
        "--tech",
        "mr2",
        "--method",
        "volumetric",
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
        expect=5,
    )
    assert "MR2 is not signed off for volumetric" in result.output


def test_the_shop_picks_the_method_when_none_is_given(running_shop: Invoke) -> None:
    out = running_shop(
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
    ).output
    assert "volumetric" in out


def test_a_cylinder_kept_too_much_of_its_expansion(running_shop: Invoke) -> None:
    out = running_shop(
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
        "100.0",
        "--permanent",
        "11.0",
    ).output
    assert "condemn" in out
    assert "past the 10% limit" in out


def test_history_of_a_cylinder_with_nothing_on_it(running_shop: Invoke) -> None:
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
    )
    assert "no records of test" in running_shop("requal", "history", "PST/B12").output
