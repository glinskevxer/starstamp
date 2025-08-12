"""The workflow files themselves, checked the way a reviewer would read them.

There is no YAML parser in this package's dependencies and there does not need
to be: what these check is that the build says what the repository says, and
that is a matter of the text lining up.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(".github/workflows")


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text()


def test_both_workflows_are_there() -> None:
    names = sorted(path.name for path in WORKFLOWS.glob("*.yml"))
    assert names == ["ci.yml", "security.yml"]


def test_the_python_versions_match_the_package() -> None:
    pyproject = Path("pyproject.toml").read_text()
    assert 'requires-python = ">=3.12"' in pyproject
    ci = workflow("ci.yml")
    assert '"3.12"' in ci
    assert '"3.13"' in ci


def test_every_job_checks_out_and_sets_up_python() -> None:
    ci = workflow("ci.yml")
    jobs = re.findall(r"^  (\w+):\n    runs-on:", ci, flags=re.MULTILINE)
    assert len(jobs) >= 7
    assert ci.count("actions/checkout@v4") == len(jobs)
    assert ci.count("actions/setup-python@v5") == len(jobs)


def test_the_gate_the_shop_runs_locally_is_in_the_build() -> None:
    ci = workflow("ci.yml")
    for step in (
        "ruff check .",
        "ruff format --check .",
        "mypy",
        "pytest -q",
        "starstamp.tools.check_migrations",
        "starstamp.tools.check_indexes",
        "starstamp.tools.check_workflow",
        "generate_cli_reference --check",
        "starstamp.tools.check_repo",
    ):
        assert step in ci, step


def test_the_accepted_advisories_are_named_with_a_reason() -> None:
    security = workflow("security.yml")
    identifiers = re.findall(r"PYSEC-\d{4}-\d+", security)
    assert identifiers
    for identifier in set(identifiers):
        assert f"--ignore-vuln {identifier}" in security
        assert security.count(identifier) >= 3


@pytest.mark.parametrize("name", ["ci.yml", "security.yml"])
def test_the_build_installs_the_package_it_is_testing(name: str) -> None:
    """Every install line names this package or an exactly pinned tool."""
    for line in workflow(name).splitlines():
        if "pip install" not in line:
            continue
        pinned = "==" in line
        editable = "-e ." in line or '-e ".' in line
        plain = line.strip().endswith("pip install .")
        assert pinned or editable or plain, line


def test_the_coverage_floor_is_where_the_suite_actually_is() -> None:
    assert "--cov-fail-under=97" in workflow("ci.yml")


def test_every_job_has_a_timeout() -> None:
    for name in ("ci.yml", "security.yml"):
        text = workflow(name)
        jobs = re.findall(r"^  (\w+):\n    runs-on:", text, flags=re.MULTILINE)
        assert text.count("timeout-minutes:") == len(jobs), name


def test_a_second_push_cancels_the_first() -> None:
    ci = workflow("ci.yml")
    assert "concurrency:" in ci
    assert "cancel-in-progress: true" in ci
