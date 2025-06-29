from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from starstamp.cli.main import cli

Invoke = Callable[..., Result]


@pytest.fixture
def book_path(tmp_path: Path) -> Path:
    return tmp_path / "shop.sqlite3"


@pytest.fixture
def run(book_path: Path) -> Invoke:
    runner = CliRunner()

    def invoke(*args: str, expect: int | None = 0) -> Result:
        """Run the command line against this test's book.

        `expect` is the status the caller is asserting; pass None where the
        test wants the result whatever it was.
        """
        result = runner.invoke(cli, ["--book", str(book_path), *args])
        if expect is not None:
            assert result.exit_code == expect, result.output
        return result

    return invoke


@pytest.fixture
def shop(run: Invoke) -> Invoke:
    run("init")
    return run


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
        "volumetric,direct-expansion,proof,visual,acetylene",
    )
    shop(
        "tech",
        "add",
        "jt7",
        "Jesse Tovar",
        "--methods",
        "volumetric,visual,acetylene",
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
        "--valve",
        "580",
        "--on",
        "2024-06-11",
    )
    return shop
