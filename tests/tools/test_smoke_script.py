"""The build's own smoke chain, run here so it cannot drift again.

The workflow used to carry its own copy of these commands. A rule about valve
outlets arrived, the chain stopped passing, and nothing noticed until CI ran:
every test in the suite calls the command line with arguments that already
suit the rules, so none of them could have found it. The chain lives in
scripts/smoke.sh now, and this runs it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/smoke.sh")


def test_the_script_is_there_and_runnable() -> None:
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK)
    assert SCRIPT.read_text().startswith("#!/usr/bin/env bash")


def test_the_build_runs_this_script_rather_than_its_own_copy() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()
    assert "scripts/smoke.sh" in workflow
    assert "starstamp --book shop.sqlite3 init" not in workflow


def test_it_stops_on_the_first_failure() -> None:
    assert "set -euo pipefail" in SCRIPT.read_text()


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_a_whole_day_goes_through_it(tmp_path: Path) -> None:
    """Run the chain against the console script this interpreter provides."""
    console = Path(sys.executable).parent / "starstamp"
    if not console.exists():
        pytest.skip("the console script is not installed in this environment")
    environment = dict(os.environ)
    environment["PATH"] = f"{console.parent}{os.pathsep}{environment['PATH']}"
    result = subprocess.run(
        ["bash", str(SCRIPT), str(tmp_path / "work")],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "smoke ok" in result.stdout
    assert "volumetric pass" in result.stdout
    assert "may be filled with nitrogen" in result.stdout
    assert (tmp_path / "work" / "shop.sqlite3").exists()
