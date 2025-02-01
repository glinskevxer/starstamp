import csv
import io
from pathlib import Path

import pytest

from .conftest import DAY, Invoke


@pytest.fixture
def tested(running_shop: Invoke) -> Invoke:
    running_shop(
        "requal",
        "run",
        "NCI/A4471",
        "--tech",
        "jt7",
        "--system",
        "WJ-1",
        "--on",
        DAY,
        "--applied",
        "3358",
        "--total",
        "110.0",
        "--permanent",
        "2.0",
    )
    return running_shop


def parse(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def test_exporting_cylinders(tested: Invoke) -> None:
    rows = parse(tested("export", "cylinders").output)
    assert rows[0]["cylinder"] == "NCI/A4471"
    assert rows[0]["owner"] == "WELD1"


def test_exporting_cylinders_for_one_account(tested: Invoke) -> None:
    rows = parse(tested("export", "cylinders", "--owner", "weld1").output)
    assert len(rows) == 1


def test_exporting_records(tested: Invoke) -> None:
    rows = parse(tested("export", "records", "--from", "2024-06-01", "--to", "2024-06-30").output)
    assert rows[0]["method"] == "volumetric"


def test_exporting_to_a_file(tested: Invoke, tmp_path: Path) -> None:
    target = tmp_path / "cylinders.csv"
    out = tested("export", "cylinders", "--out", str(target)).output
    assert f"wrote 1 rows to {target}" in out
    assert "NCI/A4471" in target.read_text()


def test_exporting_invoices_when_there_are_none(tested: Invoke) -> None:
    text = tested("export", "invoices", "weld1").output
    assert text.startswith("invoice,owner")
    assert len(parse(text)) == 0


def test_the_records_window_defaults_to_this_month(tested: Invoke) -> None:
    rows = parse(tested("--today", "2024-06-30", "export", "records").output)
    assert len(rows) == 1
