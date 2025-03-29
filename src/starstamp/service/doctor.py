"""Everything that can be checked, checked at once.

The shop runs this before an audit and after anything that went wrong. It is
deliberately a service rather than a command so that the checks can be called
from a test and asserted on, which is how the checks themselves stay honest.

Each check reports its own name, so a run that says nothing about a check is a
run where that check did not happen, rather than one where it passed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.service.integrity import IntegrityService, Severity
from starstamp.store import maintenance
from starstamp.store.db import Book
from starstamp.store.migrations import discover, pending, schema_version


@dataclass(frozen=True)
class CheckResult:
    """One check, and what it found."""

    name: str
    passed: bool
    detail: str

    def __str__(self) -> str:
        mark = "ok" if self.passed else "FAILED"
        return f"{mark}  {self.name}: {self.detail}"


@dataclass(frozen=True)
class Report:
    """Every check, in the order they were run."""

    results: tuple[CheckResult, ...]

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        return tuple(item for item in self.results if not item.passed)

    @property
    def is_clean(self) -> bool:
        return not self.failures

    def describe(self) -> str:
        lines = [str(result) for result in self.results]
        if self.is_clean:
            lines.append(f"{len(self.results)} checks, nothing to answer for")
        else:
            lines.append(f"{len(self.failures)} of {len(self.results)} checks failed")
        return "\n".join(lines)


class Doctor:
    def __init__(self, book: Book) -> None:
        self.book = book

    def run(self, today: date) -> Report:
        return Report(
            (
                self._schema(),
                self._file(),
                self._records(today),
            )
        )

    def _schema(self) -> CheckResult:
        shipped = len(discover())
        applied = schema_version(self.book.connection)
        outstanding = pending(self.book.connection)
        if outstanding:
            names = ", ".join(item.name for item in outstanding)
            return CheckResult("schema", False, f"{len(outstanding)} migrations to apply: {names}")
        return CheckResult("schema", True, f"{applied} of {shipped} applied")

    def _file(self) -> CheckResult:
        result = maintenance.verify(self.book)
        return CheckResult("file", result.is_sound, result.describe())

    def _records(self, today: date) -> CheckResult:
        report = IntegrityService(self.book).run(today)
        if report.is_clean:
            return CheckResult("records", True, f"{report.checked} cylinders, nothing odd")
        problems = len(report.problems)
        warnings = len(report.findings) - problems
        detail = f"{problems} problems, {warnings} warnings"
        first = report.findings[0]
        if first.severity is Severity.PROBLEM or problems == 0:
            detail = f"{detail}; {first}"
        return CheckResult("records", problems == 0, detail)
