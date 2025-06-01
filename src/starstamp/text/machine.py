"""Output for something other than a person.

The shop's own scripts read exit statuses, which is enough for a yes or a no.
What they cannot do is read a table, so the few commands whose answer is worth
acting on programmatically can print JSON instead.

Only the shapes that are actually consumed are here. A generic dataclass to
JSON converter would cover everything and commit the package to keeping every
field name stable forever, which is a promise nothing needs.
"""

from __future__ import annotations

import json
from datetime import date
from fractions import Fraction
from typing import Any


def encode(value: Any) -> Any:
    """Turn the values this package uses into ones json understands."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Fraction):
        return float(value)
    if isinstance(value, dict):
        return {str(key): encode(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [encode(item) for item in value]
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return value


def dumps(payload: dict[str, Any]) -> str:
    """One object per line, sorted, so a diff of two runs reads."""
    return json.dumps(encode(payload), sort_keys=True, indent=2)


def fill_decision(decision: Any) -> dict[str, Any]:
    return {
        "cylinder": decision.cylinder_key,
        "gas": decision.gas.code,
        "day": decision.day,
        "allowed": decision.allowed,
        "terminal": decision.terminal,
        "refusals": list(decision.refusals),
        "due": None if decision.due is None else decision.due.long_form(),
        "max_pressure_psig": (
            None if decision.max_pressure is None else decision.max_pressure.psig
        ),
        "filling_density_percent": decision.filling_density_percent,
    }


def integrity_report(report: Any) -> dict[str, Any]:
    return {
        "cylinders_checked": report.checked,
        "clean": report.is_clean,
        "problems": [
            {
                "check": finding.check,
                "subject": finding.subject,
                "detail": finding.detail,
            }
            for finding in report.problems
        ],
        "warnings": [
            {
                "check": finding.check,
                "subject": finding.subject,
                "detail": finding.detail,
            }
            for finding in report.findings
            if not finding.severity.is_problem
        ],
    }


def forecast(built: Any) -> dict[str, Any]:
    return {
        "from": built.from_day,
        "cylinders": built.cylinders,
        "value": str(built.value),
        "overdue": built.overdue,
        "months": [
            {
                "month": month.month.long_form(),
                "cylinders": month.cylinders,
                "value": str(month.value),
                "by_owner": month.by_owner,
            }
            for month in built.months
        ],
    }


def book_stats(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(sorted(payload.items()))
