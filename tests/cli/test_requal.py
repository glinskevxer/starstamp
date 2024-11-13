import pytest

from starstamp.cli.requal import build_readings, parse_defect
from starstamp.errors import ValidationError
from starstamp.model.defect import DefectKind

from .conftest import Invoke


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
