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

    def invoke(*args: str, expect: int = 0) -> Result:
        result = runner.invoke(cli, ["--book", str(book_path), *args])
        assert result.exit_code == expect, result.output
        return result

    return invoke


@pytest.fixture
def shop(run: Invoke) -> Invoke:
    run("init")
    return run
