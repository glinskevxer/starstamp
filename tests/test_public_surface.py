"""What this package offers the outside world, held still.

The command line is the product, but the modules are imported by the shop's
own scripts often enough that moving one is a breaking change. These are the
names that are not allowed to move without somebody deciding to move them,
and the shapes a caller is entitled to rely on.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import starstamp

PACKAGES = (
    "starstamp.model",
    "starstamp.rules",
    "starstamp.service",
    "starstamp.store",
    "starstamp.reporting",
    "starstamp.cli",
    "starstamp.text",
    "starstamp.tools",
)

ENTRY_POINTS = (
    ("starstamp.cli.main", "run"),
    ("starstamp.cli.main", "cli"),
    ("starstamp.store.db", "open_book"),
    ("starstamp.store.migrations", "migrate"),
    ("starstamp.service.requalify", "RequalificationService"),
    ("starstamp.service.fill", "FillService"),
    ("starstamp.service.doctor", "Doctor"),
    ("starstamp.errors", "StarstampError"),
)


def test_the_package_says_its_version() -> None:
    assert starstamp.__version__
    assert starstamp.__version__.count(".") == 2


@pytest.mark.parametrize("name", PACKAGES)
def test_every_package_imports(name: str) -> None:
    assert importlib.import_module(name)


@pytest.mark.parametrize(("module", "attribute"), ENTRY_POINTS)
def test_the_entry_points_are_where_they_were(module: str, attribute: str) -> None:
    imported = importlib.import_module(module)
    assert hasattr(imported, attribute), f"{module}.{attribute}"


def test_every_module_imports_on_its_own() -> None:
    """Nothing depends on being imported after something else."""
    failures: list[str] = []
    for package_name in PACKAGES:
        package = importlib.import_module(package_name)
        for info in pkgutil.iter_modules(package.__path__):
            name = f"{package_name}.{info.name}"
            try:
                importlib.import_module(name)
            except Exception as exc:  # noqa: BLE001 - the failure is the finding
                failures.append(f"{name}: {exc}")
    assert failures == []


def test_the_error_hierarchy_is_one_tree() -> None:
    from starstamp.errors import (
        ConflictError,
        NotFoundError,
        RuleViolationError,
        StarstampError,
        ValidationError,
    )

    for kind in (ValidationError, NotFoundError, ConflictError, RuleViolationError):
        assert issubclass(kind, StarstampError)
    assert issubclass(StarstampError, Exception)


def test_a_rule_violation_carries_its_citation() -> None:
    from starstamp.errors import RuleViolationError

    error = RuleViolationError("no", "49 CFR 180.205")
    assert error.citation == "49 CFR 180.205"
    assert "180.205" in str(error)


def test_nothing_ships_a_star_import() -> None:
    """A star import makes the public surface whatever happened to be defined."""
    from pathlib import Path

    offenders: list[str] = []
    for path in Path("src/starstamp").rglob("*.py"):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if line.strip().startswith("from ") and line.strip().endswith("import *"):
                offenders.append(f"{path}:{number}")
    assert offenders == []


def test_the_command_line_runs_from_a_cold_import() -> None:
    from click.testing import CliRunner

    from starstamp.cli.main import cli

    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Records for a cylinder requalification shop" in result.output
