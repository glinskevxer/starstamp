"""What the package says about itself, checked against what it is.

A version that disagrees with itself is the sort of thing nobody notices until
a shop reports a bug against a build that does not exist. These read the
metadata rather than trusting it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import starstamp

PYPROJECT = Path("pyproject.toml")


def metadata() -> dict[str, object]:
    with PYPROJECT.open("rb") as handle:
        payload = tomllib.load(handle)
    project: dict[str, object] = payload["project"]
    return project


def test_the_version_agrees_with_itself() -> None:
    assert metadata()["version"] == starstamp.__version__


def test_the_package_is_marked_as_typed() -> None:
    marker = Path("src/starstamp/py.typed")
    assert marker.exists()
    assert "Typing :: Typed" in metadata()["classifiers"]  # type: ignore[operator]


def test_the_runtime_dependency_is_pinned_exactly() -> None:
    dependencies = metadata()["dependencies"]
    assert dependencies == ["click==8.1.8"]


def test_every_development_dependency_is_pinned_exactly() -> None:
    extras = metadata()["optional-dependencies"]
    assert isinstance(extras, dict)
    for requirement in extras["dev"]:
        assert "==" in requirement, requirement


def test_the_console_script_points_at_something_that_exists() -> None:
    scripts = metadata()["scripts"]
    assert isinstance(scripts, dict)
    module, _, attribute = scripts["starstamp"].partition(":")
    imported = __import__(module, fromlist=[attribute])
    assert callable(getattr(imported, attribute))


def test_the_readme_is_the_one_that_is_there() -> None:
    assert metadata()["readme"] == "README.md"
    assert Path("README.md").read_text().startswith("# starstamp")


def test_the_python_versions_are_the_ones_the_build_runs() -> None:
    assert metadata()["requires-python"] == ">=3.12"
    classifiers = metadata()["classifiers"]
    assert isinstance(classifiers, list)
    assert "Programming Language :: Python :: 3.12" in classifiers
    assert "Programming Language :: Python :: 3.13" in classifiers


@pytest.mark.parametrize("field", ["description", "keywords", "authors", "license"])
def test_the_metadata_a_person_reads_is_filled_in(field: str) -> None:
    assert metadata()[field]
