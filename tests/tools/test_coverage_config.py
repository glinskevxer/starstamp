"""The coverage job measures subprocesses, so it has to hand them the config.

The smoke test drives the console script twenty five times, and pytest-cov
starts coverage inside every one of those children. It tells each child what
to measure through the environment, and with no `--cov-config` on the command
line the variable it sets says "no config file at all". The child then takes
coverage's defaults and records statements. The parent, whose config file is
resolved the ordinary way, falls back to pyproject.toml and records branches.
The run dies combining the two, and it dies after every test has passed.

None of this shows up in an ordinary `pytest` run, because coverage is off
there. It appears only in the one job that measures, which is the job least
likely to be run by hand.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import coverage

CI = Path(".github/workflows/ci.yml")

CHILD = """
import coverage

measure = coverage.Coverage()
measure.start()
import json  # noqa: E402
measure.stop()
measure.save()
print("branch" if measure.get_data().has_arcs() else "statement")
"""


def test_the_default_config_does_not_record_branches() -> None:
    """The whole mechanism. With no config file a child measures statements."""
    assert coverage.Coverage(config_file=False).config.branch is False


def test_this_project_records_branches() -> None:
    assert coverage.Coverage(config_file="pyproject.toml").config.branch is True


def test_the_coverage_job_names_the_config_file() -> None:
    """The fix, asserted on the file the build actually runs."""
    for line in CI.read_text().splitlines():
        if "--cov" not in line:
            continue
        assert "--cov-config=" in line, line


def child_mode(work: Path, config: str) -> str:
    """Start coverage in a child the way pytest-cov's own hook starts it."""
    script = work / "child.py"
    script.write_text(CHILD)
    environment = {"PATH": "/usr/bin:/bin"}
    if config:
        environment["COVERAGE_RCFILE"] = config
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "COVERAGE_RCFILE": config}
        if config
        else {"PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_a_child_given_no_config_measures_statements(tmp_path: Path) -> None:
    """The positive control. This is the state that broke the build."""
    assert child_mode(tmp_path, "") == "statement"


def test_a_child_given_this_project_config_measures_branches(tmp_path: Path) -> None:
    assert child_mode(tmp_path, str(Path("pyproject.toml").resolve())) == "branch"
