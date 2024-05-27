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
