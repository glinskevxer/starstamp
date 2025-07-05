from pathlib import Path

import pytest

from starstamp.cli.requal import build_readings, parse_defect
from starstamp.errors import ValidationError
from starstamp.model.defect import DefectKind

from .conftest import DAY, Invoke


@pytest.fixture
def bench(shop: Invoke) -> Invoke:
    shop("account", "add", "weld1", "Cascade Welding Supply")
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
    )
    return shop


def test_defects_parse_from_the_command_line() -> None:
    observation = parse_defect("pitting:0.016")
    assert observation.kind is DefectKind.ISOLATED_PITTING
    assert observation.depth_thousandths_in == 16
    full = parse_defect("line corrosion:0.030:3.500:below the collar")
    assert full.length_thousandths_in == 3500
    assert full.note == "below the collar"
    bare = parse_defect("crack")
    assert bare.depth_thousandths_in is None


def test_readings_need_a_pressure() -> None:
    assert build_readings(None, 30, None, None, False, False) is None
    with pytest.raises(ValidationError, match="need the pressure"):
        build_readings(None, 30, "120.0", "6.0", False, False)


def test_readings_build() -> None:
    readings = build_readings("3358", 30, "120.0", "6.0", False, True)
    assert readings is not None
    assert readings.distorted
    assert readings.permanent_percentage > 0


def test_a_scan_parses_off_the_command_line() -> None:
    from starstamp.cli.requal import parse_scan

    scan = parse_scan("M1:0.215, M2:0.214,L1:0.210")
    assert scan.count == 3
    assert scan.thinnest.thousandths_in == 210


def test_a_scan_point_without_a_thickness() -> None:
    from starstamp.cli.requal import parse_scan

    with pytest.raises(ValidationError, match="POSITION:INCHES"):
        parse_scan("M1")


def test_an_empty_scan() -> None:
    from starstamp.cli.requal import parse_scan

    with pytest.raises(ValidationError, match="not a scan"):
        parse_scan(" , ")


def test_pounds_parse() -> None:
    from starstamp.cli.requal import parse_pounds

    assert parse_pounds("84.70") == 8470
    assert parse_pounds(" 84 lb ") == 8400
    assert parse_pounds("84.7") == 8470


@pytest.mark.parametrize("text", ["", "84.705", "eighty", "-84"])
def test_bad_pounds(text: str) -> None:
    from starstamp.cli.requal import parse_pounds

    with pytest.raises(ValidationError, match="pounds to two places"):
        parse_pounds(text)


def test_an_acetylene_finding_needs_a_weight() -> None:
    from starstamp.cli.requal import build_acetylene

    assert build_acetylene(None, False, False, False, False) is None
    with pytest.raises(ValidationError, match="needs the cylinder weighed"):
        build_acetylene(None, True, False, False, False)


def test_the_weighing_builds() -> None:
    from starstamp.cli.requal import build_acetylene

    exam = build_acetylene("84.70", True, False, False, True)
    assert exam is not None
    assert exam.tare_now_hundredths_lb == 8470
    assert not exam.fuse_plugs_sound
    assert not exam.cap_sound


def test_the_sheet_template(shop: Invoke) -> None:
    out = shop("requal", "sheet", "--rows", "0").output
    assert out.strip() == "cylinder,applied,total,permanent,hold,defects"


def test_a_batch_through_the_command_line(running_shop: Invoke, tmp_path: Path) -> None:
    path = tmp_path / "sheet.csv"
    path.write_text("cylinder,applied,total,permanent,hold,defects\nNCI/A4471,3358,110.0,2.0,30,\n")
    out = running_shop(
        "requal",
        "batch",
        str(path),
        "--tech",
        "jt7",
        "--system",
        "WJ-1",
        "--on",
        "2024-06-12",
    ).output
    assert "1 recorded, 1 passed" in out
    assert "volumetric pass" in out


def test_a_batch_with_a_bad_row(running_shop: Invoke, tmp_path: Path) -> None:
    path = tmp_path / "sheet.csv"
    path.write_text(
        "cylinder,applied,total,permanent\nNCI/A4471,3358,110.0,2.0\nNOPE/X1,3358,110.0,2.0\n"
    )
    out = running_shop(
        "requal",
        "batch",
        str(path),
        "--tech",
        "jt7",
        "--system",
        "WJ-1",
        "--on",
        "2024-06-12",
    ).output
    assert "1 rows left out" in out
    assert "no cylinder NOPE/X1" in out


def test_a_batch_with_the_wrong_columns(running_shop: Invoke, tmp_path: Path) -> None:
    path = tmp_path / "sheet.csv"
    path.write_text("cylinder\nNCI/A4471\n")
    running_shop("requal", "batch", str(path), "--tech", "jt7", "--system", "WJ-1", expect=1)


def test_what_is_due(running_shop: Invoke) -> None:
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
    out = running_shop("requal", "due", "--on", "2034-04-01", "--within", "3").output
    assert "NCI/A4471" in out
    assert "06-34" in out


def test_a_cylinder_that_was_never_tested_is_on_the_due_list(running_shop: Invoke) -> None:
    out = running_shop("requal", "due", "--on", "2024-06-12").output
    assert "never tested" in out
    assert "NCI/A4471" in out


def test_the_method_is_planned_against_a_badge(running_shop: Invoke) -> None:
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
    out = running_shop(
        "requal", "due", "--on", "2024-06-12", "--within", "200", "--tech", "jt7"
    ).output
    assert "volumetric" in out


def test_a_cylinder_nobody_on_the_bench_can_do(running_shop: Invoke) -> None:
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
    running_shop(
        "tech",
        "add",
        "ac1",
        "Only Acetylene",
        "--methods",
        "acetylene",
        "--from",
        "2022-03-01",
    )
    out = running_shop(
        "requal", "due", "--on", "2024-06-12", "--within", "200", "--tech", "ac1"
    ).output
    assert "none:" in out
