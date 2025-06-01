"""The commands that can answer a script instead of a person."""

from __future__ import annotations

import json
from typing import Any

from .conftest import DAY, Invoke


def parse(text: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(text)
    return payload


def test_stats_as_json(running_shop: Invoke) -> None:
    payload = parse(running_shop("stats", "--json").output)
    assert payload["cylinders"] == 1
    assert payload["records_of_test"] == 0
    assert payload["by_status"] == {"in_service": 1}
    assert payload["schema"] > 0


def test_the_check_as_json(running_shop: Invoke) -> None:
    payload = parse(running_shop("check", "--json").output)
    assert payload["clean"] is True
    assert payload["problems"] == []
    assert payload["cylinders_checked"] == 1


def test_a_warning_shows_in_the_json(running_shop: Invoke) -> None:
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
        "--defect",
        "bulge",
    )
    result = running_shop("check", "--on", "2024-06-13", "--json", expect=8)
    payload = parse(result.output)
    assert payload["clean"] is False
    assert payload["problems"] == []
    assert "written to" in payload["warnings"][0]["detail"]


def test_a_fill_decision_as_json(running_shop: Invoke) -> None:
    result = running_shop("fill", "check", "NCI/A4471", "--json", expect=6)
    payload = parse(result.output)
    assert payload["allowed"] is False
    assert payload["gas"] == "N2"
    assert "no standing requalification" in payload["refusals"]
    assert payload["due"] is None


def test_a_good_fill_decision_as_json(running_shop: Invoke) -> None:
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
    payload = parse(
        running_shop("--today", "2024-07-01", "fill", "check", "NCI/A4471", "--json").output
    )
    assert payload["allowed"] is True
    assert payload["due"] == "2034-06"
    assert payload["max_pressure_psig"] == 2217


def test_the_forecast_as_json(running_shop: Invoke) -> None:
    running_shop("price", "set", "REQUAL_WJ", "14.50", "--from", "2023-01-01")
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
    payload = parse(running_shop("report", "forecast", "--on", "2034-01-01", "--json").output)
    assert payload["cylinders"] == 1
    assert payload["months"][0]["month"] == "2034-06"
    assert payload["months"][0]["by_owner"] == {"WELD1": 1}
    assert payload["value"] == "14.50"


def test_the_json_is_stable_across_runs(running_shop: Invoke) -> None:
    first = running_shop("stats", "--json").output
    second = running_shop("stats", "--json").output
    assert first == second
