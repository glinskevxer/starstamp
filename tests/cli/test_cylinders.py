from pathlib import Path

import pytest

from .conftest import Invoke


@pytest.fixture
def stocked(shop: Invoke) -> Invoke:
    shop("account", "add", "weld1", "Cascade Welding Supply", "--opened", "2019-04-01")
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


LIST = """cylinder,specification,manufactured,service,ree,wall
PST/B12,DOT-3AA2015,06-98,N2,31.2,0.220
B13,DOT-3AA2015,06-98,N2,,
PST/B14,DOT-4BA240,09-05,LPG,,0.087
"""


def test_a_dry_run_import(stocked: Invoke, tmp_path: Path) -> None:
    path = tmp_path / "fleet.csv"
    path.write_text(LIST)
    out = stocked("cylinder", "import", str(path), "--owner", "weld1").output
    assert "would take in 2 cylinders" in out
    assert "1 rows left out" in out
    assert "nothing was written" in out
    assert "PST/B12" not in stocked("cylinder", "list").output


def test_a_written_import(stocked: Invoke, tmp_path: Path) -> None:
    path = tmp_path / "fleet.csv"
    path.write_text(LIST)
    out = stocked("cylinder", "import", str(path), "--owner", "weld1", "--write").output
    assert "took in 2 cylinders" in out
    assert "PST/B12" in stocked("cylinder", "list").output


def test_an_import_of_a_list_with_no_columns(stocked: Invoke, tmp_path: Path) -> None:
    path = tmp_path / "junk.csv"
    path.write_text("a,b\n1,2\n")
    stocked("cylinder", "import", str(path), "--owner", "weld1", expect=4)


def test_an_import_for_an_account_that_is_not_there(stocked: Invoke, tmp_path: Path) -> None:
    path = tmp_path / "fleet.csv"
    path.write_text(LIST)
    stocked("cylinder", "import", str(path), "--owner", "nope", expect=3)


def test_the_template_has_the_columns_the_import_wants(shop: Invoke, tmp_path: Path) -> None:
    text = shop("cylinder", "template", "--rows", "0").output
    assert text.strip() == "cylinder,specification,manufactured,service,ree,wall"


def test_the_template_example_row_imports_cleanly(stocked: Invoke, tmp_path: Path) -> None:
    text = stocked("cylinder", "template").output.replace("NCI/A4471", "PST/A9001")
    path = tmp_path / "template.csv"
    path.write_text(text)
    out = stocked("cylinder", "import", str(path), "--owner", "weld1", "--write").output
    assert "took in 1 cylinders" in out


def test_the_import_day_lands_on_the_record(stocked: Invoke, tmp_path: Path) -> None:
    path = tmp_path / "fleet.csv"
    path.write_text("cylinder,specification,manufactured,service\nPST/B20,DOT-3AA2015,06-98,N2\n")
    stocked("cylinder", "import", str(path), "--owner", "weld1", "--on", "2024-05-04", "--write")
    assert "PST/B20" in stocked("cylinder", "list").output


def test_the_valve_is_shown(stocked: Invoke) -> None:
    stocked("cylinder", "valve", "NCI/A4471", "580", "--on", "2024-06-11")
    assert "CGA 580" in stocked("cylinder", "show", "NCI/A4471").output


def test_asking_which_valve_a_cylinder_takes(stocked: Invoke) -> None:
    out = stocked("cylinder", "valve", "NCI/A4471").output
    assert "fitted none recorded, takes CGA 580" in out


def test_fitting_a_valve_the_shop_does_not_stock(stocked: Invoke) -> None:
    stocked("cylinder", "valve", "NCI/A4471", "999", expect=2)


def test_changing_the_service_drops_the_valve(stocked: Invoke) -> None:
    stocked("cylinder", "valve", "NCI/A4471", "580", "--on", "2024-06-11")
    out = stocked("cylinder", "service", "NCI/A4471", "O2").output
    assert "now in oxygen service and needs CGA 540" in out
    assert "fitted none recorded" in stocked("cylinder", "valve", "NCI/A4471").output


def test_a_valve_change_needs_a_technician_on_the_bench(stocked: Invoke) -> None:
    result = stocked(
        "repair",
        "do",
        "NCI/A4471",
        "valve",
        "--tech",
        "jt7",
        "--on",
        "2024-06-14",
        "--parts",
        "CGA 580 brass",
        expect=3,
    )
    assert "no technician JT7" in result.output


def test_the_life_of_a_cylinder(stocked: Invoke) -> None:
    stocked("cylinder", "wall", "NCI/A4471", "0.214", "--on", "2024-06-11")
    out = stocked("--today", "2024-06-20", "cylinder", "life", "NCI/A4471").output
    assert "0.214 in from ultrasonic sweep" in out
    assert "26 years" in out


def test_the_life_of_a_cylinder_nothing_happened_to(stocked: Invoke) -> None:
    assert "nothing has happened to it here" in stocked("cylinder", "life", "NCI/A4471").output


def test_filtering_the_life(stocked: Invoke) -> None:
    stocked("cylinder", "wall", "NCI/A4471", "0.214", "--on", "2024-06-11")
    out = stocked("cylinder", "life", "NCI/A4471", "--only", "wall").output
    assert "0.214" in out
    assert (
        "nothing of that kind" in stocked("cylinder", "life", "NCI/A4471", "--only", "test").output
    )


def test_the_age_profile(stocked: Invoke) -> None:
    out = stocked("--today", "2024-06-20", "cylinder", "age").output
    assert "1990s" in out
    assert "oldest is NCI/A4471" in out
    assert "26 years" in out


def test_the_age_profile_of_an_empty_book(shop: Invoke) -> None:
    assert "no cylinders" in shop("cylinder", "age").output


def test_finding_cylinders(stocked: Invoke) -> None:
    out = stocked("cylinder", "find", "--owner", "weld1").output
    assert "NCI/A4471" in out
    assert "1 cylinders" in out


def test_finding_by_specification_and_age(stocked: Invoke) -> None:
    assert "NCI/A4471" in stocked("cylinder", "find", "--spec", "3aa").output
    assert "nothing matches" in stocked("cylinder", "find", "--spec", "3al").output
    assert "NCI/A4471" in stocked("cylinder", "find", "--made-before", "2000-01").output
    assert "nothing matches" in stocked("cylinder", "find", "--made-after", "2000-01").output


def test_finding_by_a_status_that_is_not_one(stocked: Invoke) -> None:
    stocked("cylinder", "find", "--status", "wobbly", expect=2)


def test_the_ownership_history(stocked: Invoke) -> None:
    assert "never changed hands" in stocked("cylinder", "owners", "NCI/A4471").output
    stocked("account", "add", "fire7", "Sanpete Fire", "--opened", "2020-01-01")
    stocked(
        "cylinder",
        "transfer",
        "NCI/A4471",
        "fire7",
        "--on",
        "2024-06-20",
        "--note",
        "sold with the business",
    )
    out = stocked("cylinder", "owners", "NCI/A4471").output
    assert "belongs to FIRE7" in out
    assert "WELD1 to FIRE7" in out
    assert "sold with the business" in out


def test_transferring_to_the_same_account(stocked: Invoke) -> None:
    stocked("cylinder", "transfer", "NCI/A4471", "weld1", expect=4)
