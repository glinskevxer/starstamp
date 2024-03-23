import pytest

from .conftest import Invoke


@pytest.fixture
def stocked(shop: Invoke) -> Invoke:
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
        "31.2",
        "--water-capacity",
        "43.5",
        "--tare",
        "117.5",
        "--wall",
        "0.220",
    )
    return shop


def test_register_and_show(stocked: Invoke) -> None:
    out = stocked("cylinder", "show", "nci/a4471").output
    assert "DOT-3AA2015" in out
    assert "1998-06" in out
    assert "nitrogen" in out
    assert "3358 psig" in out
    assert "direct expansion, volumetric" in out


def test_register_needs_a_known_account(shop: Invoke) -> None:
    shop(
        "cylinder",
        "register",
        "NCI/A1",
        "--owner",
        "NOPE",
        "--spec",
        "DOT-3AA2015",
        "--dom",
        "06-98",
        "--service",
        "N2",
        expect=3,
    )


def test_register_refuses_a_gas_the_book_does_not_know(shop: Invoke) -> None:
    shop("account", "add", "weld1", "Cascade")
    shop(
        "cylinder",
        "register",
        "NCI/A1",
        "--owner",
        "WELD1",
        "--spec",
        "DOT-3AA2015",
        "--dom",
        "06-98",
        "--service",
        "krypton",
        expect=2,
    )


def test_list_by_owner_and_status(stocked: Invoke) -> None:
    assert "NCI/A4471" in stocked("cylinder", "list", "--owner", "weld1").output
    assert "no cylinders" in stocked("cylinder", "list", "--status", "condemned").output


def test_list_of_an_empty_book(shop: Invoke) -> None:
    assert "no cylinders" in shop("cylinder", "list").output


def test_wall_reading(stocked: Invoke) -> None:
    assert "0.214" in stocked("cylinder", "wall", "NCI/A4471", "0.214").output
    assert "214" in stocked("cylinder", "show", "NCI/A4471").output


def test_transfer(stocked: Invoke) -> None:
    stocked("account", "add", "fire7", "Sanpete Fire")
    out = stocked("cylinder", "transfer", "NCI/A4471", "fire7").output
    assert "now belongs to FIRE7" in out


def test_status_moves(stocked: Invoke) -> None:
    assert "is in_shop" in stocked("cylinder", "status", "NCI/A4471", "in_shop").output
    stocked("cylinder", "status", "NCI/A4471", "wobbly", expect=2)


def test_an_acetylene_cylinder_shows_no_test_pressure(shop: Invoke) -> None:
    shop("account", "add", "weld1", "Cascade")
    shop(
        "cylinder",
        "register",
        "NCI/AC1",
        "--owner",
        "WELD1",
        "--spec",
        "DOT-8AL",
        "--dom",
        "04-05",
        "--service",
        "C2H2",
    )
    out = shop("cylinder", "show", "NCI/AC1").output
    assert "test pressure  -" in out
    assert "acetylene visual" in out
