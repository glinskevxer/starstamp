"""The house rules this repository keeps, checked mechanically.

Three of them, all of which have been broken here at least once:

Every module says what it is for in its first line. A module with no docstring
is one somebody added in a hurry, and this package's docstrings are where the
domain reasoning lives.

No markers left behind. A TODO in a shop's records system is a decision
somebody deferred and nobody came back to.

Every source package has a matching test package. It does not check that every
module is tested, which would be a lie dressed as a number; it checks that a
whole area of the code has not appeared with no tests beside it at all.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

SOURCE = Path("src/starstamp")
TESTS = Path("tests")
MARKERS = ("TODO", "FIXME", "XXX", "HACK")
EXEMPT_FROM_TESTS = {"starstamp", "cli", "text", "tools"}


@dataclass(frozen=True)
class Complaint:
    """One house rule, broken once."""

    rule: str
    where: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.where}: {self.detail}"


def modules(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in str(path))


def missing_docstrings(root: Path = SOURCE) -> list[Complaint]:
    found: list[Complaint] = []
    for path in modules(root):
        if path.name == "__init__.py" and path.read_text().strip() == "":
            continue
        tree = ast.parse(path.read_text())
        if not ast.get_docstring(tree):
            found.append(Complaint("docstring", str(path), "no module docstring"))
    return found


def leftover_markers(roots: tuple[Path, ...] = (SOURCE, TESTS)) -> list[Complaint]:
    found: list[Complaint] = []
    for root in roots:
        for path in modules(root):
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                for marker in MARKERS:
                    if f"{marker}:" in line or f"# {marker}" in line:
                        found.append(Complaint("marker", f"{path}:{number}", line.strip()))
    return found


def packages_without_tests(source: Path = SOURCE, tests: Path = TESTS) -> list[Complaint]:
    found: list[Complaint] = []
    for path in sorted(source.iterdir()):
        if not path.is_dir() or path.name.startswith("_"):
            continue
        if path.name in EXEMPT_FROM_TESTS:
            continue
        if not (tests / path.name).is_dir():
            found.append(Complaint("tests", str(path), f"no tests/{path.name} beside it"))
    return found


def run(argv: list[str] | None = None) -> int:
    _ = argv
    complaints = missing_docstrings() + leftover_markers() + packages_without_tests()
    counted = len(modules(SOURCE)) + len(modules(TESTS))
    print(f"{counted} modules checked")
    for complaint in complaints:
        print(f"problem: {complaint}", file=sys.stderr)
    return 1 if complaints else 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
